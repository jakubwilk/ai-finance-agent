from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.fixed_costs.nodes import (
    make_flag_discrepancies,
    make_load_fixed_costs,
    make_match_transactions,
    make_persist_reconciliation,
)
from finance_agent.subgraphs.fixed_costs.state import FixedCostsState

LOAD_FIXED_COSTS = "load_fixed_costs"
MATCH_TRANSACTIONS = "match_transactions"
FLAG_DISCREPANCIES = "flag_discrepancies"
PERSIST_RECONCILIATION = "persist_reconciliation"


def build_fixed_costs_graph(session: AsyncSession) -> CompiledStateGraph:
    """Build the fixed costs reconciliation subgraph per
    docs/05-spec-fixed-costs.md. No Drive access needed — pure DB logic,
    runs after categorization so `Transaction.category_id` is already
    populated on candidate matches.
    """
    builder = StateGraph(FixedCostsState)

    builder.add_node(LOAD_FIXED_COSTS, make_load_fixed_costs(session))
    builder.add_node(MATCH_TRANSACTIONS, make_match_transactions(session))
    builder.add_node(FLAG_DISCREPANCIES, make_flag_discrepancies())
    builder.add_node(PERSIST_RECONCILIATION, make_persist_reconciliation(session))

    builder.add_edge(START, LOAD_FIXED_COSTS)
    builder.add_edge(LOAD_FIXED_COSTS, MATCH_TRANSACTIONS)
    builder.add_edge(MATCH_TRANSACTIONS, FLAG_DISCREPANCIES)
    builder.add_edge(FLAG_DISCREPANCIES, PERSIST_RECONCILIATION)
    builder.add_edge(PERSIST_RECONCILIATION, END)

    return builder.compile()
