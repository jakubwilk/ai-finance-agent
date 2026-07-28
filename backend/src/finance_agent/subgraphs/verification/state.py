from datetime import date

from typing_extensions import TypedDict


class StatementCheck(TypedDict):
    """Pre-check result for one `STATEMENTS` row (docs/03-spec-statement-verification.md)."""

    statement_id: str
    is_readable: bool
    period_start: date | None
    period_end: date | None
    is_duplicate: bool
    failure_reason: str | None


class VerificationState(TypedDict):
    """State for the verification pre-check subgraph.

    `results` has no reducer — each node rewrites the same list in this
    linear pipeline (same style as ingestion's `to_download`), refining one
    field at a time rather than accumulating across parallel writers.
    """

    results: list[StatementCheck]
    all_ok: bool
