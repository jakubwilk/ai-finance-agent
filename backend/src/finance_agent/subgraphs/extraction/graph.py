from collections.abc import Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.extraction.nodes import (
    _extract_text_and_words,
    make_parse_statement,
    make_persist_transactions,
)
from finance_agent.subgraphs.extraction.parsers.base import StatementParser, Word
from finance_agent.subgraphs.extraction.state import ExtractionState
from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient

PARSE_STATEMENT = "parse_statement"
PERSIST_TRANSACTIONS = "persist_transactions"


def build_extraction_graph(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    extract_text_and_words: Callable[
        [bytes], tuple[list[str], list[list[Word]]]
    ] = _extract_text_and_words,
    parsers: tuple[StatementParser, ...] | None = None,
) -> CompiledStateGraph:
    """Build the extraction subgraph per docs/04-spec-transaction-extraction.md.

    Only parses statements with `status == "verified"` (i.e. already passed
    pre-check, docs/03) — leaves status as `"verified"`; post-check
    (PLAN.md step 4) is what moves it to `"processed"`/`"failed"`.
    """
    builder = StateGraph(ExtractionState)

    builder.add_node(
        PARSE_STATEMENT,
        make_parse_statement(session, drive_client, extract_text_and_words, parsers),
    )
    builder.add_node(PERSIST_TRANSACTIONS, make_persist_transactions(session))

    builder.add_edge(START, PARSE_STATEMENT)
    builder.add_edge(PARSE_STATEMENT, PERSIST_TRANSACTIONS)
    builder.add_edge(PERSIST_TRANSACTIONS, END)

    return builder.compile()
