"""Node factories for the verification pre-check subgraph
(docs/03-spec-statement-verification.md).

Same DI pattern as `subgraphs.ingestion.nodes`: each `make_*` closes over
its dependencies and returns the async node callable, so tests can inject a
fake session/drive client.

`read_statement` deliberately merges two conceptual spec steps
(`check_readability` + reading the period) into one node — both need the
same pdfplumber parse of the same downloaded bytes, so splitting them across
a node boundary would mean either re-downloading/re-parsing twice or
carrying raw PDF bytes through graph state (which ingestion's `download`
node specifically avoids, see subgraphs/ingestion/state.py).

pdfplumber's text/table extraction (`_extract_text_and_tables`) is kept as a
thin, separate seam from the pure parsing logic (`_is_readable`,
`_extract_period`, `_parse_date`) so the latter can be unit-tested with
plain Python strings/lists mimicking pdfplumber's output shape, without
needing real PDF bytes in tests.
"""

import io
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

import pdfplumber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Statement
from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient
from finance_agent.subgraphs.verification.state import StatementCheck, VerificationState

Node = Callable[[VerificationState], Awaitable[dict]]

# "Od dnia"/"Do dnia" have no Polish diacritics, so this label match is
# unaffected by any PDF text-encoding quirks in the rest of the document.
_PERIOD_START_LABEL = "Od dnia"
_PERIOD_END_LABEL = "Do dnia"


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _is_readable(text: str) -> bool:
    return bool(text.strip())


def _extract_period(
    tables: list[list[list[str | None]]],
) -> tuple[date | None, date | None]:
    period_start: date | None = None
    period_end: date | None = None
    for table in tables:
        for row in table:
            if not row or not row[0]:
                continue
            label = row[0].strip()
            if label == _PERIOD_START_LABEL and len(row) > 1 and row[1]:
                period_start = _parse_date(row[1])
            elif label == _PERIOD_END_LABEL and len(row) > 1 and row[1]:
                period_end = _parse_date(row[1])
    return period_start, period_end


def _extract_text_and_tables(
    content: bytes,
) -> tuple[str, list[list[list[str | None]]]]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text_parts = [page.extract_text() or "" for page in pdf.pages]
        tables: list[list[list[str | None]]] = []
        for page in pdf.pages:
            tables.extend(page.extract_tables())
    return "\n".join(text_parts), tables


def make_read_statement(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    extract_text_and_tables: Callable[
        [bytes], tuple[str, list[list[list[str | None]]]]
    ] = _extract_text_and_tables,
) -> Node:
    """`extract_text_and_tables` defaults to the real pdfplumber-based
    extractor; tests inject a fake returning canned (text, tables) tuples so
    they don't need to construct real PDF bytes with a genuine text layer.
    """

    async def _read_statement(_state: VerificationState) -> dict:
        pending = (
            (
                await session.execute(
                    select(Statement).where(Statement.status == "pending")
                )
            )
            .scalars()
            .all()
        )

        results: list[StatementCheck] = []
        for statement in pending:
            content = drive_client.download_file(statement.drive_file_id)
            try:
                text, tables = extract_text_and_tables(content)
                is_readable = _is_readable(text)
            except Exception:  # noqa: BLE001 -- any parse failure means unreadable, regardless of the underlying pdfplumber/pdfminer exception type
                is_readable = False
                tables = []
            period_start, period_end = (
                _extract_period(tables) if is_readable else (None, None)
            )

            failure_reason = None
            if not is_readable:
                failure_reason = "unreadable_pdf"
            elif period_start is None or period_end is None:
                failure_reason = "unparseable_period"

            results.append(
                StatementCheck(
                    statement_id=str(statement.id),
                    is_readable=is_readable,
                    period_start=period_start,
                    period_end=period_end,
                    is_duplicate=False,
                    failure_reason=failure_reason,
                )
            )

        return {"results": results}

    return _read_statement


def make_check_duplicate(session: AsyncSession) -> Node:
    async def _check_duplicate(state: VerificationState) -> dict:
        updated: list[StatementCheck] = []
        for result in state["results"]:
            if result["failure_reason"] is not None:
                updated.append(result)
                continue

            existing = await session.execute(
                select(Statement.id).where(
                    Statement.status.in_(("verified", "processed")),
                    Statement.id != uuid.UUID(result["statement_id"]),
                    Statement.period_start <= result["period_end"],
                    Statement.period_end >= result["period_start"],
                )
            )
            if existing.scalars().first() is not None:
                updated.append(
                    {
                        **result,
                        "is_duplicate": True,
                        "failure_reason": "duplicate_statement",
                    }
                )
            else:
                updated.append(result)

        return {"results": updated}

    return _check_duplicate


def make_mark_result(session: AsyncSession) -> Node:
    async def _mark_result(state: VerificationState) -> dict:
        for result in state["results"]:
            statement = await session.get(Statement, uuid.UUID(result["statement_id"]))
            if result["failure_reason"] is not None:
                statement.status = "failed"
                statement.failure_reason = result["failure_reason"]
            else:
                statement.status = "verified"
                statement.period_start = result["period_start"]
                statement.period_end = result["period_end"]
                statement.verified_at = datetime.now(UTC)

        await session.flush()

        all_ok = all(result["failure_reason"] is None for result in state["results"])
        return {"results": state["results"], "all_ok": all_ok}

    return _mark_result
