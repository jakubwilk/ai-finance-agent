from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.investment.nodes import (
    make_assess_trend,
    make_check_safety_buffer,
    make_generate_allocation_proposal,
    make_persist_recommendation,
)
from finance_agent.subgraphs.investment.state import InvestmentState

CHECK_SAFETY_BUFFER = "check_safety_buffer"
ASSESS_TREND = "assess_trend"
GENERATE_ALLOCATION_PROPOSAL = "generate_allocation_proposal"
PERSIST_RECOMMENDATION = "persist_recommendation"


def build_investment_graph(session: AsyncSession, chat_model) -> CompiledStateGraph:
    """Build the investment analysis subgraph per
    docs/08-spec-investment-analysis.md. No Drive access needed — pure DB +
    LLM logic, runs after cashflow_calculation.
    """
    builder = StateGraph(InvestmentState)

    builder.add_node(CHECK_SAFETY_BUFFER, make_check_safety_buffer(session))
    builder.add_node(ASSESS_TREND, make_assess_trend(session))
    builder.add_node(
        GENERATE_ALLOCATION_PROPOSAL,
        make_generate_allocation_proposal(chat_model, session),
    )
    builder.add_node(PERSIST_RECOMMENDATION, make_persist_recommendation(session))

    builder.add_edge(START, CHECK_SAFETY_BUFFER)
    builder.add_edge(CHECK_SAFETY_BUFFER, ASSESS_TREND)
    builder.add_edge(ASSESS_TREND, GENERATE_ALLOCATION_PROPOSAL)
    builder.add_edge(GENERATE_ALLOCATION_PROPOSAL, PERSIST_RECOMMENDATION)
    builder.add_edge(PERSIST_RECOMMENDATION, END)

    return builder.compile()
