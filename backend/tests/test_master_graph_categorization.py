"""Proves the exact LangGraph mechanism `_categorization_node`
(`graph/master.py`) relies on: a node function that calls
`.ainvoke()` on a SEPARATELY compiled subgraph (not mounted via a literal
`builder.add_node(name, compiled_subgraph)`, since `CategorizationState` and
`MasterGraphState` share no keys) still correctly pauses the OUTER graph on
`interrupt()`, resumable via `Command(resume=...)` on the outer thread_id —
verified directly against LangGraph's docs/source before this design was
adopted (see `_make_categorization_node`'s docstring).

Deliberately synthetic (no DB, no real `categorization` subgraph): the real
`_categorization_node` always opens its session via the module-level
`async_session_factory`, which is hardwired to `DATABASE_URL` (the dev DB,
same as every other real master-graph node) — there's no DI seam yet to
point it at `TEST_DATABASE_URL` instead, and adding one wasn't justified by
a concrete need beyond this test (PLAN.md step 13's FastAPI layer will need
real per-request session DI anyway, which is the natural place to add it).
Categorization's OWN business logic (rule_match/llm_classify/confidence_gate/
human_review/persist_category) is already thoroughly tested against a real
test DB in `tests/test_categorization_graph.py`. What's tested here is the
one thing that was genuinely uncertain: whether the *nesting pattern itself*
propagates interrupts correctly — a pure LangGraph mechanics question,
independent of what the nested subgraph's nodes actually do.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class InnerState(TypedDict):
    items: list[str]


class OuterState(TypedDict):
    visited: list[str]


def _inner_step_one(_state: InnerState) -> dict:
    return {"items": ["a"]}


def _inner_needs_review(state: InnerState) -> dict:
    if not state["items"]:
        return {}
    decision = interrupt({"items": state["items"]})
    return {"items": [f"reviewed:{decision}"]}


def build_inner_graph():
    """Mirrors `build_categorization_graph`'s shape: no `checkpointer=`
    passed, so it inherits whatever checkpointer is driving the current
    invocation.
    """
    builder = StateGraph(InnerState)
    builder.add_node("step_one", _inner_step_one)
    builder.add_node("needs_review", _inner_needs_review)
    builder.add_edge(START, "step_one")
    builder.add_edge("step_one", "needs_review")
    builder.add_edge("needs_review", END)
    return builder.compile()


async def _outer_node(_state: OuterState) -> dict:
    """Mirrors `_categorization_node`: builds the inner subgraph fresh and
    calls `.ainvoke()` on it directly, not via `add_node`.
    """
    inner_graph = build_inner_graph()
    await inner_graph.ainvoke({"items": []})
    return {"visited": ["outer_node"]}


def build_outer_graph(checkpointer):
    """Mirrors `build_master_graph`: a real, explicit checkpointer at the
    top level.
    """
    builder = StateGraph(OuterState)
    builder.add_node("outer_node", _outer_node)
    builder.add_edge(START, "outer_node")
    builder.add_edge("outer_node", END)
    return builder.compile(checkpointer=checkpointer)


async def test_nested_interrupt_pauses_the_outer_graph():
    checkpointer = InMemorySaver()
    graph = build_outer_graph(checkpointer)
    config = {"configurable": {"thread_id": "thread-1"}}

    result = await graph.ainvoke({"visited": []}, config)

    assert "__interrupt__" in result
    # outer_node's own return value never happened — it's still paused
    # inside the nested inner_graph.ainvoke() call.
    assert result["visited"] == []


async def test_resume_completes_the_outer_graph():
    checkpointer = InMemorySaver()
    graph = build_outer_graph(checkpointer)
    config = {"configurable": {"thread_id": "thread-2"}}

    await graph.ainvoke({"visited": []}, config)
    result = await graph.ainvoke(Command(resume="approved"), config)

    assert "__interrupt__" not in result
    assert result["visited"] == ["outer_node"]


async def test_no_pending_review_completes_without_pausing():
    """If the inner graph has nothing to review, it never calls
    `interrupt()` — the outer graph should complete in a single call, same
    as categorization when nothing needs a human.
    """

    def _no_items_step_one(_state: InnerState) -> dict:
        return {"items": []}

    def build_no_op_inner_graph():
        builder = StateGraph(InnerState)
        builder.add_node("step_one", _no_items_step_one)
        builder.add_node("needs_review", _inner_needs_review)
        builder.add_edge(START, "step_one")
        builder.add_edge("step_one", "needs_review")
        builder.add_edge("needs_review", END)
        return builder.compile()

    async def _outer_node_no_op(_state: OuterState) -> dict:
        inner_graph = build_no_op_inner_graph()
        await inner_graph.ainvoke({"items": []})
        return {"visited": ["outer_node"]}

    checkpointer = InMemorySaver()
    builder = StateGraph(OuterState)
    builder.add_node("outer_node", _outer_node_no_op)
    builder.add_edge(START, "outer_node")
    builder.add_edge("outer_node", END)
    graph = builder.compile(checkpointer=checkpointer)

    result = await graph.ainvoke(
        {"visited": []}, {"configurable": {"thread_id": "thread-3"}}
    )

    assert "__interrupt__" not in result
    assert result["visited"] == ["outer_node"]


async def test_get_state_history_returns_full_step_history():
    checkpointer = InMemorySaver()
    graph = build_outer_graph(checkpointer)
    config = {"configurable": {"thread_id": "thread-4"}}

    await graph.ainvoke({"visited": []}, config)
    await graph.ainvoke(Command(resume="approved"), config)

    history = [state async for state in graph.aget_state_history(config)]

    assert len(history) >= 2
    # newest checkpoint first, per LangGraph's own ordering.
    assert history[0].values["visited"] == ["outer_node"]
