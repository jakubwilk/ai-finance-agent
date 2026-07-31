from decimal import Decimal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.categorization.nodes import (
    DEFAULT_THRESHOLD,
    make_confidence_gate,
    make_human_review,
    make_llm_classify,
    make_persist_category,
    make_rule_match,
)
from finance_agent.subgraphs.categorization.state import CategorizationState

RULE_MATCH = "rule_match"
LLM_CLASSIFY = "llm_classify"
CONFIDENCE_GATE = "confidence_gate"
HUMAN_REVIEW = "human_review"
PERSIST_CATEGORY = "persist_category"


def build_categorization_graph(
    session: AsyncSession,
    chat_model,
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    threshold: Decimal = DEFAULT_THRESHOLD,
) -> CompiledStateGraph:
    """Build the categorization subgraph per docs/06-spec-categorization.md.

    `checkpointer` defaults to `None`: when this subgraph is invoked from
    inside a master-graph node function (`graph/master.py`'s
    `_categorization_node`, PLAN.md step 12), it inherits the currently
    running master graph's own checkpointer automatically — interrupts
    propagate to the top-level graph regardless of nesting, verified
    directly against LangGraph's docs/source before relying on it. Pass an
    explicit checkpointer (e.g. `InMemorySaver()`, see
    `tests/test_categorization_graph.py`) only when invoking this subgraph
    standalone, outside the master graph.
    """
    builder = StateGraph(CategorizationState)

    builder.add_node(RULE_MATCH, make_rule_match(session))
    builder.add_node(LLM_CLASSIFY, make_llm_classify(session, chat_model))
    builder.add_node(CONFIDENCE_GATE, make_confidence_gate(threshold))
    builder.add_node(HUMAN_REVIEW, make_human_review())
    builder.add_node(PERSIST_CATEGORY, make_persist_category(session))

    builder.add_edge(START, RULE_MATCH)
    builder.add_edge(RULE_MATCH, LLM_CLASSIFY)
    builder.add_edge(LLM_CLASSIFY, CONFIDENCE_GATE)
    builder.add_edge(CONFIDENCE_GATE, HUMAN_REVIEW)
    builder.add_edge(HUMAN_REVIEW, PERSIST_CATEGORY)
    builder.add_edge(PERSIST_CATEGORY, END)

    return builder.compile(checkpointer=checkpointer)
