from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from finance_agent.graph.state import MasterGraphState

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


def build_master_graph() -> CompiledStateGraph:
    """Build the master orchestration graph per docs/11-spec-orchestration-scheduling.md.

    Every node is currently a placeholder — this chunk only establishes the
    graph shape (nodes + edges + branching) so it renders and executes
    correctly; real subgraph logic is added incrementally in later
    PLAN.md steps. No checkpointer is attached yet (arrives with Postgres).
    """
    builder = StateGraph(MasterGraphState)

    for node_name in (
        INGESTION,
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
