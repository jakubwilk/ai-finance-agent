from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.cashflow.nodes import (
    make_aggregate_income_expense,
    make_apply_fixed_costs_status,
    make_breakdown_by_category,
    make_compute_rolling_month,
    make_compute_surplus,
)
from finance_agent.subgraphs.cashflow.state import CashflowState

AGGREGATE_INCOME_EXPENSE = "aggregate_income_expense"
BREAKDOWN_BY_CATEGORY = "breakdown_by_category"
APPLY_FIXED_COSTS_STATUS = "apply_fixed_costs_status"
COMPUTE_SURPLUS = "compute_surplus"
COMPUTE_ROLLING_MONTH = "compute_rolling_month"


def build_cashflow_graph(session: AsyncSession) -> CompiledStateGraph:
    """Build the cashflow calculation subgraph per
    docs/07-spec-cashflow-calculation.md. No Drive access needed — pure DB
    logic, runs after fixed_costs_reconciliation so
    `Transaction.matched_fixed_cost_id` is already populated where
    applicable.
    """
    builder = StateGraph(CashflowState)

    builder.add_node(AGGREGATE_INCOME_EXPENSE, make_aggregate_income_expense(session))
    builder.add_node(BREAKDOWN_BY_CATEGORY, make_breakdown_by_category(session))
    builder.add_node(APPLY_FIXED_COSTS_STATUS, make_apply_fixed_costs_status(session))
    builder.add_node(COMPUTE_SURPLUS, make_compute_surplus())
    builder.add_node(COMPUTE_ROLLING_MONTH, make_compute_rolling_month(session))

    builder.add_edge(START, AGGREGATE_INCOME_EXPENSE)
    builder.add_edge(AGGREGATE_INCOME_EXPENSE, BREAKDOWN_BY_CATEGORY)
    builder.add_edge(BREAKDOWN_BY_CATEGORY, APPLY_FIXED_COSTS_STATUS)
    builder.add_edge(APPLY_FIXED_COSTS_STATUS, COMPUTE_SURPLUS)
    builder.add_edge(COMPUTE_SURPLUS, COMPUTE_ROLLING_MONTH)
    builder.add_edge(COMPUTE_ROLLING_MONTH, END)

    return builder.compile()
