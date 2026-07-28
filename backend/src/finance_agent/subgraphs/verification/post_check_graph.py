from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.verification.post_check_nodes import (
    make_check_balance_consistency,
    make_mark_result,
)
from finance_agent.subgraphs.verification.post_check_state import PostCheckState

CHECK_BALANCE_CONSISTENCY = "check_balance_consistency"
MARK_RESULT = "mark_result"


def build_post_check_graph(session: AsyncSession) -> CompiledStateGraph:
    """Build the verification **post-check** subgraph per
    docs/03-spec-statement-verification.md (step 4) — runs after extraction
    (docs/04), validates `opening_balance + Σamount == closing_balance`.
    No Drive access needed here, unlike pre-check.
    """
    builder = StateGraph(PostCheckState)

    builder.add_node(CHECK_BALANCE_CONSISTENCY, make_check_balance_consistency(session))
    builder.add_node(MARK_RESULT, make_mark_result(session))

    builder.add_edge(START, CHECK_BALANCE_CONSISTENCY)
    builder.add_edge(CHECK_BALANCE_CONSISTENCY, MARK_RESULT)
    builder.add_edge(MARK_RESULT, END)

    return builder.compile()
