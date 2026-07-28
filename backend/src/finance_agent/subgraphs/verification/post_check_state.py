from typing_extensions import TypedDict


class PostCheckResult(TypedDict):
    """Post-check result for one `STATEMENTS` row (docs/03-spec-statement-verification.md)."""

    statement_id: str
    is_consistent: bool
    failure_reason: str | None


class PostCheckState(TypedDict):
    """State for the verification post-check subgraph. `results` has no
    reducer — same linear-pipeline style as pre-check/ingestion/extraction.
    """

    results: list[PostCheckResult]
    all_ok: bool
