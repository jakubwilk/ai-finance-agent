from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.reporting.nodes import (
    make_determine_report_types,
    make_persist_report,
    make_render_monthly,
    make_render_weekly,
)
from finance_agent.subgraphs.reporting.state import ReportingState

DETERMINE_REPORT_TYPES = "determine_report_types"
RENDER_WEEKLY = "render_weekly"
RENDER_MONTHLY = "render_monthly"
PERSIST_REPORT = "persist_report"


def build_reporting_graph(session: AsyncSession) -> CompiledStateGraph:
    """Build the reporting subgraph per docs/09-spec-reporting.md. No Drive
    access needed — pure DB + templating logic, runs after
    investment_analysis.
    """
    builder = StateGraph(ReportingState)

    builder.add_node(DETERMINE_REPORT_TYPES, make_determine_report_types(session))
    builder.add_node(RENDER_WEEKLY, make_render_weekly(session))
    builder.add_node(RENDER_MONTHLY, make_render_monthly(session))
    builder.add_node(PERSIST_REPORT, make_persist_report(session))

    builder.add_edge(START, DETERMINE_REPORT_TYPES)
    builder.add_edge(DETERMINE_REPORT_TYPES, RENDER_WEEKLY)
    builder.add_edge(RENDER_WEEKLY, RENDER_MONTHLY)
    builder.add_edge(RENDER_MONTHLY, PERSIST_REPORT)
    builder.add_edge(PERSIST_REPORT, END)

    return builder.compile()
