from finance_agent.graph.master import (
    ALERT_IMMEDIATE,
    CASHFLOW_CALCULATION,
    CATEGORIZATION,
    EMAIL_DELIVERY,
    EXTRACTION,
    FIXED_COSTS_RECONCILIATION,
    HUMAN_REVIEW,
    INGESTION,
    INVESTMENT_ANALYSIS,
    REPORTING,
    VERIFICATION_POST_CHECK,
    VERIFICATION_PRE_CHECK,
    _make_placeholder,
    build_master_graph,
)

# The 3 behavioral tests below only care about branching logic, not the real
# ingestion subgraph (which needs a DB session + Drive client) — inject the
# same cheap placeholder every other node uses, so these stay pure, fast,
# sync unit tests invocable via `.invoke()`.
_PLACEHOLDER_INGESTION_NODE = _make_placeholder(INGESTION)

ALL_NODES = [
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
]


def test_master_graph_compiles():
    build_master_graph()


def test_mermaid_contains_every_node():
    graph = build_master_graph()
    mermaid = graph.get_graph().draw_mermaid()

    assert mermaid
    for node in ALL_NODES:
        assert node in mermaid


def test_happy_path_reaches_end_without_review():
    graph = build_master_graph(ingestion_node=_PLACEHOLDER_INGESTION_NODE)

    result = graph.invoke(
        {"verification_ok": True, "needs_review": False, "visited": []}
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


def test_happy_path_with_needs_review_routes_through_human_review():
    graph = build_master_graph(ingestion_node=_PLACEHOLDER_INGESTION_NODE)

    result = graph.invoke(
        {"verification_ok": True, "needs_review": True, "visited": []}
    )

    assert HUMAN_REVIEW in result["visited"]
    assert (
        result["visited"].index(HUMAN_REVIEW)
        == result["visited"].index(CATEGORIZATION) + 1
    )
    assert (
        result["visited"].index(FIXED_COSTS_RECONCILIATION)
        == result["visited"].index(HUMAN_REVIEW) + 1
    )


def test_verification_pre_check_failure_routes_to_alert_and_ends():
    graph = build_master_graph(ingestion_node=_PLACEHOLDER_INGESTION_NODE)

    result = graph.invoke(
        {"verification_ok": False, "needs_review": False, "visited": []}
    )

    assert result["visited"] == [INGESTION, VERIFICATION_PRE_CHECK, ALERT_IMMEDIATE]
    assert EXTRACTION not in result["visited"]
