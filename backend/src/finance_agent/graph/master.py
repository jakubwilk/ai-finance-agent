from collections.abc import Awaitable, Callable
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from finance_agent.config import settings
from finance_agent.db.session import async_session_factory
from finance_agent.graph.state import MasterGraphState
from finance_agent.subgraphs.ingestion.drive_client import build_drive_client
from finance_agent.subgraphs.ingestion.graph import build_ingestion_graph

INGESTION = "ingestion"
VERIFICATION_PRE_CHECK = "verification_pre_check"
EXTRACTION = "extraction"
VERIFICATION_POST_CHECK = "verification_post_check"
CATEGORIZATION = "categorization"
HUMAN_REVIEW = "human_review"
FIXED_COSTS_RECONCILIATION = "fixed_costs_reconciliation"
CASHFLOW_CALCULATION = "cashflow_calculation"
INVESTMENT_ANALYSIS = "investment_analysis"
REPORTING = "reporting"
EMAIL_DELIVERY = "email_delivery"
ALERT_IMMEDIATE = "alert_immediate"


def _make_placeholder(node_name: str):
    """No-op stand-in for a real subgraph, wired in a later PLAN.md step.

    Records its own name in `visited` so tests can assert which path
    through the graph actually ran.
    """

    def _placeholder(state: MasterGraphState) -> dict:
        return {"visited": [node_name]}

    return _placeholder


async def _ingestion_node(_state: MasterGraphState) -> dict:
    """Real `ingestion` subgraph, wired in place of the placeholder.

    Opens one session per run, builds a real Drive client from settings,
    and commits only if the whole subgraph succeeds — mirrors the
    try/except/commit/rollback shape in scripts/seed_reference_data.py.
    This is the master graph's first async node: LangGraph requires
    `ainvoke`, not `invoke`, once any node is async.
    """
    async with async_session_factory() as session:
        try:
            drive_client = build_drive_client(settings)
            ingestion_graph = build_ingestion_graph(
                session=session,
                drive_client=drive_client,
                folder_id=settings.google_drive_folder_id,
            )
            await ingestion_graph.ainvoke(
                {"discovered": [], "to_download": [], "ingested": []}
            )
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [INGESTION]}


def _route_after_verification_pre_check(
    state: MasterGraphState,
) -> Literal["extraction", "alert_immediate"]:
    return EXTRACTION if state["verification_ok"] else ALERT_IMMEDIATE


def _route_after_verification_post_check(
    state: MasterGraphState,
) -> Literal["categorization", "alert_immediate"]:
    return CATEGORIZATION if state["verification_ok"] else ALERT_IMMEDIATE


def _route_after_categorization(
    state: MasterGraphState,
) -> Literal["human_review", "fixed_costs_reconciliation"]:
    return HUMAN_REVIEW if state["needs_review"] else FIXED_COSTS_RECONCILIATION


def build_master_graph(
    *,
    ingestion_node: Callable[[MasterGraphState], Awaitable[dict]] = _ingestion_node,
) -> CompiledStateGraph:
    """Build the master orchestration graph per docs/11-spec-orchestration-scheduling.md.

    Every node except `ingestion` is currently a placeholder — this chunk
    only establishes the graph shape (nodes + edges + branching) so it
    renders and executes correctly; real subgraph logic is added
    incrementally in later PLAN.md steps. No checkpointer is attached yet
    (arrives with Postgres).

    `ingestion_node` defaults to the real subgraph wrapper (`_ingestion_node`,
    async — requires `graph.ainvoke(...)`, not `.invoke()`); tests that only
    care about branching logic can override it with a cheap sync placeholder
    to stay hermetic and invocable via sync `.invoke()`.
    """
    builder = StateGraph(MasterGraphState)

    for node_name in (
        VERIFICATION_PRE_CHECK,
        EXTRACTION,
        VERIFICATION_POST_CHECK,
        CATEGORIZATION,
        HUMAN_REVIEW,
        FIXED_COSTS_RECONCILIATION,
        CASHFLOW_CALCULATION,
        INVESTMENT_ANALYSIS,
        REPORTING,
        EMAIL_DELIVERY,
        ALERT_IMMEDIATE,
    ):
        builder.add_node(node_name, _make_placeholder(node_name))
    builder.add_node(INGESTION, ingestion_node)

    builder.add_edge(START, INGESTION)
    builder.add_edge(INGESTION, VERIFICATION_PRE_CHECK)
    builder.add_conditional_edges(
        VERIFICATION_PRE_CHECK,
        _route_after_verification_pre_check,
        [EXTRACTION, ALERT_IMMEDIATE],
    )
    builder.add_edge(EXTRACTION, VERIFICATION_POST_CHECK)
    builder.add_conditional_edges(
        VERIFICATION_POST_CHECK,
        _route_after_verification_post_check,
        [CATEGORIZATION, ALERT_IMMEDIATE],
    )
    builder.add_conditional_edges(
        CATEGORIZATION,
        _route_after_categorization,
        [HUMAN_REVIEW, FIXED_COSTS_RECONCILIATION],
    )
    builder.add_edge(HUMAN_REVIEW, FIXED_COSTS_RECONCILIATION)
    builder.add_edge(FIXED_COSTS_RECONCILIATION, CASHFLOW_CALCULATION)
    builder.add_edge(CASHFLOW_CALCULATION, INVESTMENT_ANALYSIS)
    builder.add_edge(INVESTMENT_ANALYSIS, REPORTING)
    builder.add_edge(REPORTING, EMAIL_DELIVERY)
    builder.add_edge(EMAIL_DELIVERY, END)
    builder.add_edge(ALERT_IMMEDIATE, END)

    return builder.compile()
