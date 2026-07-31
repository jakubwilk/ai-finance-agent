from finance_agent.graph.master import (
    ALERT_IMMEDIATE,
    CASHFLOW_CALCULATION,
    CATEGORIZATION,
    EMAIL_DELIVERY,
    EXTRACTION,
    FIXED_COSTS_RECONCILIATION,
    INGESTION,
    INVESTMENT_ANALYSIS,
    REPORTING,
    VERIFICATION_POST_CHECK,
    VERIFICATION_PRE_CHECK,
    _make_placeholder,
    build_master_graph,
)

# The behavioral tests below only care about branching logic, not the real
# subgraphs (which need a DB session and, for some, a Drive client/chat
# model) — inject the same cheap placeholder every other node uses, so
# these stay pure, fast, sync unit tests invocable via `.invoke()`.
_PLACEHOLDER_INGESTION_NODE = _make_placeholder(INGESTION)
_PLACEHOLDER_VERIFICATION_PRE_CHECK_NODE = _make_placeholder(VERIFICATION_PRE_CHECK)
_PLACEHOLDER_EXTRACTION_NODE = _make_placeholder(EXTRACTION)
_PLACEHOLDER_VERIFICATION_POST_CHECK_NODE = _make_placeholder(VERIFICATION_POST_CHECK)
_PLACEHOLDER_CATEGORIZATION_NODE = _make_placeholder(CATEGORIZATION)
_PLACEHOLDER_FIXED_COSTS_RECONCILIATION_NODE = _make_placeholder(
    FIXED_COSTS_RECONCILIATION
)
_PLACEHOLDER_CASHFLOW_CALCULATION_NODE = _make_placeholder(CASHFLOW_CALCULATION)
_PLACEHOLDER_INVESTMENT_ANALYSIS_NODE = _make_placeholder(INVESTMENT_ANALYSIS)
_PLACEHOLDER_REPORTING_NODE = _make_placeholder(REPORTING)
_PLACEHOLDER_EMAIL_DELIVERY_NODE = _make_placeholder(EMAIL_DELIVERY)
_PLACEHOLDER_ALERT_IMMEDIATE_NODE = _make_placeholder(ALERT_IMMEDIATE)

ALL_NODES = [
    INGESTION,
    VERIFICATION_PRE_CHECK,
    EXTRACTION,
    VERIFICATION_POST_CHECK,
    CATEGORIZATION,
    FIXED_COSTS_RECONCILIATION,
    CASHFLOW_CALCULATION,
    INVESTMENT_ANALYSIS,
    REPORTING,
    EMAIL_DELIVERY,
    ALERT_IMMEDIATE,
]


def test_master_graph_compiles():
    build_master_graph()


def test_mermaid_contains_every_node():
    graph = build_master_graph()
    mermaid = graph.get_graph().draw_mermaid()

    assert mermaid
    for node in ALL_NODES:
        assert node in mermaid


def test_happy_path_reaches_end():
    graph = build_master_graph(
        ingestion_node=_PLACEHOLDER_INGESTION_NODE,
        verification_pre_check_node=_PLACEHOLDER_VERIFICATION_PRE_CHECK_NODE,
        extraction_node=_PLACEHOLDER_EXTRACTION_NODE,
        verification_post_check_node=_PLACEHOLDER_VERIFICATION_POST_CHECK_NODE,
        categorization_node=_PLACEHOLDER_CATEGORIZATION_NODE,
        fixed_costs_reconciliation_node=_PLACEHOLDER_FIXED_COSTS_RECONCILIATION_NODE,
        cashflow_calculation_node=_PLACEHOLDER_CASHFLOW_CALCULATION_NODE,
        investment_analysis_node=_PLACEHOLDER_INVESTMENT_ANALYSIS_NODE,
        reporting_node=_PLACEHOLDER_REPORTING_NODE,
        email_delivery_node=_PLACEHOLDER_EMAIL_DELIVERY_NODE,
        alert_immediate_node=_PLACEHOLDER_ALERT_IMMEDIATE_NODE,
    )

    result = graph.invoke(
        {
            "verification_ok": True,
            "alert_details": [],
            "visited": [],
        }
    )

    assert result["visited"] == [
        INGESTION,
        VERIFICATION_PRE_CHECK,
        EXTRACTION,
        VERIFICATION_POST_CHECK,
        CATEGORIZATION,
        FIXED_COSTS_RECONCILIATION,
        CASHFLOW_CALCULATION,
        INVESTMENT_ANALYSIS,
        REPORTING,
        EMAIL_DELIVERY,
    ]


def test_verification_pre_check_failure_routes_to_alert_and_ends():
    graph = build_master_graph(
        ingestion_node=_PLACEHOLDER_INGESTION_NODE,
        verification_pre_check_node=_PLACEHOLDER_VERIFICATION_PRE_CHECK_NODE,
        extraction_node=_PLACEHOLDER_EXTRACTION_NODE,
        verification_post_check_node=_PLACEHOLDER_VERIFICATION_POST_CHECK_NODE,
        categorization_node=_PLACEHOLDER_CATEGORIZATION_NODE,
        fixed_costs_reconciliation_node=_PLACEHOLDER_FIXED_COSTS_RECONCILIATION_NODE,
        cashflow_calculation_node=_PLACEHOLDER_CASHFLOW_CALCULATION_NODE,
        investment_analysis_node=_PLACEHOLDER_INVESTMENT_ANALYSIS_NODE,
        reporting_node=_PLACEHOLDER_REPORTING_NODE,
        email_delivery_node=_PLACEHOLDER_EMAIL_DELIVERY_NODE,
        alert_immediate_node=_PLACEHOLDER_ALERT_IMMEDIATE_NODE,
    )

    result = graph.invoke(
        {
            "verification_ok": False,
            "alert_details": [{"statement_id": "test-id", "failure_reason": "test"}],
            "visited": [],
        }
    )

    assert result["visited"] == [INGESTION, VERIFICATION_PRE_CHECK, ALERT_IMMEDIATE]
    assert EXTRACTION not in result["visited"]
