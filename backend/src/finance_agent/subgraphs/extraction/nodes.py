"""Node factories for the extraction subgraph (docs/04-spec-transaction-extraction.md).

Same DI pattern as ingestion/verification: each `make_*` closes over its
dependencies and returns the async node callable.
"""

import io
import uuid
from collections.abc import Awaitable, Callable

import pdfplumber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Statement, Transaction
from finance_agent.subgraphs.extraction.parsers.base import StatementParser, Word
from finance_agent.subgraphs.extraction.parsers.generic import GenericLineParser
from finance_agent.subgraphs.extraction.parsers.pko_bp import (
    PkoBpHistoriaRachunkuParser,
)
from finance_agent.subgraphs.extraction.state import (
    ExtractionState,
    StatementTransactions,
)
from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient

Node = Callable[[ExtractionState], Awaitable[dict]]

# Ordered strategy-pattern registry (docs/04) — first match wins, generic
# fallback always matches so it must stay last.
DEFAULT_PARSERS: tuple[StatementParser, ...] = (
    PkoBpHistoriaRachunkuParser(),
    GenericLineParser(),
)


def _extract_text_and_words(content: bytes) -> tuple[list[str], list[list[Word]]]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text_parts = [page.extract_text() or "" for page in pdf.pages]
        words_per_page = [page.extract_words() for page in pdf.pages]
    return text_parts, words_per_page


def make_parse_statement(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    extract_text_and_words: Callable[
        [bytes], tuple[list[str], list[list[Word]]]
    ] = _extract_text_and_words,
    parsers: tuple[StatementParser, ...] | None = None,
) -> Node:
    """`extract_text_and_words` defaults to the real pdfplumber-based
    extractor; tests inject a fake returning canned (text_parts,
    words_per_page) so they don't need real PDF bytes. `parsers` defaults to
    `DEFAULT_PARSERS`.
    """
    active_parsers = parsers if parsers is not None else DEFAULT_PARSERS

    async def _parse_statement(_state: ExtractionState) -> dict:
        verified = (
            (
                await session.execute(
                    select(Statement).where(Statement.status == "verified")
                )
            )
            .scalars()
            .all()
        )

        pending: list[StatementTransactions] = []
        for statement in verified:
            content = drive_client.download_file(statement.drive_file_id)
            text_parts, words_per_page = extract_text_and_words(content)
            first_page_text = text_parts[0] if text_parts else ""
            full_text = "\n".join(text_parts)

            parser = next(
                (p for p in active_parsers if p.matches(first_page_text)), None
            )
            transactions = parser.parse(full_text, words_per_page) if parser else []

            pending.append(
                StatementTransactions(
                    statement_id=str(statement.id), transactions=transactions
                )
            )

        return {"pending": pending}

    return _parse_statement


def make_persist_transactions(session: AsyncSession) -> Node:
    async def _persist_transactions(state: ExtractionState) -> dict:
        for entry in state["pending"]:
            transactions = entry["transactions"]
            for txn in transactions:
                session.add(
                    Transaction(
                        statement_id=uuid.UUID(entry["statement_id"]),
                        txn_date=txn["txn_date"],
                        amount=txn["amount"],
                        description=txn["description"],
                        counterparty=txn["counterparty"],
                        running_balance=txn["running_balance"],
                        review_status="auto",
                        raw_details=txn["raw_details"],
                    )
                )

            if transactions:
                statement = await session.get(
                    Statement, uuid.UUID(entry["statement_id"])
                )
                newest, oldest = transactions[0], transactions[-1]
                statement.closing_balance = newest["running_balance"]
                if oldest["running_balance"] is not None:
                    statement.opening_balance = (
                        oldest["running_balance"] - oldest["amount"]
                    )

        await session.flush()
        return {}

    return _persist_transactions
