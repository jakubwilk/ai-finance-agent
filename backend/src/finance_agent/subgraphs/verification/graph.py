from collections.abc import Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient
from finance_agent.subgraphs.verification.nodes import (
    _extract_text_and_tables,
    make_check_duplicate,
    make_mark_result,
    make_read_statement,
)
from finance_agent.subgraphs.verification.state import VerificationState

READ_STATEMENT = "read_statement"
CHECK_DUPLICATE = "check_duplicate"
MARK_RESULT = "mark_result"


def build_verification_graph(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    extract_text_and_tables: Callable[
        [bytes], tuple[str, list[list[list[str | None]]]]
    ] = _extract_text_and_tables,
) -> CompiledStateGraph:
    """Build the verification **pre-check** subgraph per
    docs/03-spec-statement-verification.md.

    Only the pre-check phase (readability, period, duplicate) — post-check
    (balance consistency) runs after extraction (docs/04, a later PLAN.md
    step) and isn't part of this subgraph. `extract_text_and_tables`
    defaults to the real pdfplumber extractor; tests override it (see
    `subgraphs.verification.nodes.make_read_statement`).
    """
    builder = StateGraph(VerificationState)

    builder.add_node(
        READ_STATEMENT,
        make_read_statement(session, drive_client, extract_text_and_tables),
    )
    builder.add_node(CHECK_DUPLICATE, make_check_duplicate(session))
    builder.add_node(MARK_RESULT, make_mark_result(session))

    builder.add_edge(START, READ_STATEMENT)
    builder.add_edge(READ_STATEMENT, CHECK_DUPLICATE)
    builder.add_edge(CHECK_DUPLICATE, MARK_RESULT)
    builder.add_edge(MARK_RESULT, END)

    return builder.compile()
