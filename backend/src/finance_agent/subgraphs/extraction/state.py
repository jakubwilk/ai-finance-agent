from typing_extensions import TypedDict

from finance_agent.subgraphs.extraction.parsers.base import RawTransaction


class StatementTransactions(TypedDict):
    statement_id: str
    transactions: list[RawTransaction]


class ExtractionState(TypedDict):
    """State for the extraction subgraph. `pending` is a plain list, no
    reducer — this is a linear pipeline (`parse_statement` produces it,
    `persist_transactions` consumes it), same style as ingestion/verification.
    """

    pending: list[StatementTransactions]
