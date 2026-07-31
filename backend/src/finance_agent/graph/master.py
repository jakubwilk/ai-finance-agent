from collections.abc import Awaitable, Callable
from email.message import EmailMessage
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.config import settings
from finance_agent.db.models import CashflowSummary
from finance_agent.db.session import async_session_factory
from finance_agent.graph.state import MasterGraphState
from finance_agent.llm.client import build_classification_model, build_investment_model
from finance_agent.subgraphs.cashflow.graph import build_cashflow_graph
from finance_agent.subgraphs.cashflow.state import CashflowState
from finance_agent.subgraphs.categorization.graph import build_categorization_graph
from finance_agent.subgraphs.email_delivery.graph import build_email_delivery_graph
from finance_agent.subgraphs.email_delivery.smtp_client import build_smtp_client
from finance_agent.subgraphs.extraction.graph import build_extraction_graph
from finance_agent.subgraphs.fixed_costs.graph import build_fixed_costs_graph
from finance_agent.subgraphs.ingestion.drive_client import build_drive_client
from finance_agent.subgraphs.ingestion.graph import build_ingestion_graph
from finance_agent.subgraphs.investment.graph import build_investment_graph
from finance_agent.subgraphs.reporting.graph import build_reporting_graph
from finance_agent.subgraphs.verification.graph import build_verification_graph
from finance_agent.subgraphs.verification.post_check_graph import (
    build_post_check_graph,
)

INGESTION = "ingestion"
VERIFICATION_PRE_CHECK = "verification_pre_check"
EXTRACTION = "extraction"
VERIFICATION_POST_CHECK = "verification_post_check"
CATEGORIZATION = "categorization"
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


def _alert_details_from_results(results: list[dict]) -> list[dict]:
    """Shared by both verification nodes below — builds
    `MasterGraphState.alert_details` from whichever pre-check/post-check
    entries actually failed, for `_alert_immediate_node` to read.
    """
    return [
        {"statement_id": r["statement_id"], "failure_reason": r["failure_reason"]}
        for r in results
        if r["failure_reason"] is not None
    ]


async def _verification_pre_check_node(_state: MasterGraphState) -> dict:
    """Real verification pre-check subgraph, wired in place of the
    placeholder. Same session/drive-client/commit-or-rollback shape as
    `_ingestion_node`.
    """
    async with async_session_factory() as session:
        try:
            drive_client = build_drive_client(settings)
            verification_graph = build_verification_graph(
                session=session, drive_client=drive_client
            )
            result = await verification_graph.ainvoke({"results": [], "all_ok": True})
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {
        "visited": [VERIFICATION_PRE_CHECK],
        "verification_ok": result["all_ok"],
        "alert_details": _alert_details_from_results(result["results"]),
    }


async def _extraction_node(_state: MasterGraphState) -> dict:
    """Real extraction subgraph, wired in place of the placeholder. Same
    session/drive-client/commit-or-rollback shape as the other real nodes.
    No routing decision here — EXTRACTION -> VERIFICATION_POST_CHECK is a
    plain edge.
    """
    async with async_session_factory() as session:
        try:
            drive_client = build_drive_client(settings)
            extraction_graph = build_extraction_graph(
                session=session, drive_client=drive_client
            )
            await extraction_graph.ainvoke({"pending": []})
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [EXTRACTION]}


async def _verification_post_check_node(_state: MasterGraphState) -> dict:
    """Real verification post-check subgraph, wired in place of the
    placeholder. No Drive client needed — pure DB arithmetic. Reuses the
    `verification_ok` key that `_route_after_verification_post_check`
    already reads.
    """
    async with async_session_factory() as session:
        try:
            post_check_graph = build_post_check_graph(session=session)
            result = await post_check_graph.ainvoke({"results": [], "all_ok": True})
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {
        "visited": [VERIFICATION_POST_CHECK],
        "verification_ok": result["all_ok"],
        "alert_details": _alert_details_from_results(result["results"]),
    }


def _make_categorization_node(
    chat_model_factory: Callable[[], object] = build_classification_model,
) -> Callable[[MasterGraphState], Awaitable[dict]]:
    """Factory for the real categorization node, wired in place of the
    placeholder (PLAN.md step 6 built the subgraph in full but left it
    unwired, pending exactly this step's checkpointer). `chat_model_factory`
    defaults to the real `build_classification_model` (called lazily inside
    the node, never at import time — same reason `_investment_analysis_node`
    calls `build_investment_model()` inside its own body, not as a default
    argument) — tests inject a factory returning a fake chat model instead,
    so the real interrupt/resume mechanics can be exercised without needing
    `OVH_AI_ENDPOINTS_*` configured.

    `CategorizationState` (`items: [...]`) shares no keys with
    `MasterGraphState`, so it can't be mounted via a literal
    `builder.add_node(name, compiled_subgraph)` — LangGraph only merges
    overlapping state keys. Verified directly against LangGraph's docs
    before relying on it: the documented fix for a disjoint-schema subgraph
    is to call it from a normal node function, exactly the same
    session-per-node shape every other real node here already uses
    (`_fixed_costs_reconciliation_node` etc.).

    No explicit `checkpointer=` passed to `build_categorization_graph` —
    when invoked from inside a currently-executing master-graph node, the
    subgraph inherits that run's checkpointer automatically, and its
    `interrupt()` (inside `human_review`) propagates up to pause the whole
    master graph, resumable via `Command(resume=...)` on the master's own
    `thread_id` — no separate categorization thread_id needed. This is also
    why the session is opened fresh here rather than held open across the
    pause: `interrupt()` returns control all the way out of `ainvoke()`,
    closing this session; resuming re-enters this function from the top
    with a brand new one (same as a completely separate run).

    The pause itself surfaces as a raised exception here (LangGraph's
    internal `GraphInterrupt`, propagating up to whichever graph is really
    driving this invocation) — caught by the same `except Exception:
    rollback(); raise` as any other failure. That's correct, not
    incidental: nothing is written to the DB before `persist_category`
    (rule_match/llm_classify/confidence_gate/human_review are all read-only
    or pure), so rolling back on the way out loses nothing, and re-raising
    is exactly what lets the interrupt keep propagating to the master
    graph's own executor.
    """

    async def _categorization_node(_state: MasterGraphState) -> dict:
        async with async_session_factory() as session:
            try:
                chat_model = chat_model_factory()
                categorization_graph = build_categorization_graph(
                    session=session, chat_model=chat_model
                )
                await categorization_graph.ainvoke({"items": []})
            except Exception:
                await session.rollback()
                raise
            await session.commit()

        return {"visited": [CATEGORIZATION]}

    return _categorization_node


_categorization_node = _make_categorization_node()


async def _fixed_costs_reconciliation_node(_state: MasterGraphState) -> dict:
    """Real fixed_costs_reconciliation subgraph, wired in place of the
    placeholder. No Drive client needed, no interrupt() — unlike
    categorization, there's no human-in-the-loop step here, so this can be
    wired directly rather than waiting for the master-graph checkpointer
    (PLAN.md step 12).
    """
    async with async_session_factory() as session:
        try:
            fixed_costs_graph = build_fixed_costs_graph(session=session)
            await fixed_costs_graph.ainvoke({"statement_id": None, "matches": []})
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [FIXED_COSTS_RECONCILIATION]}


async def _upsert_cashflow_summary(
    thread_id: str, result: CashflowState, *, session: AsyncSession
) -> CashflowSummary:
    """Get-or-create upsert into `cashflow_summaries`, keyed by `thread_id`
    (docs/13-spec-backend-api.md's `GET /runs/{thread_id}/cashflow`) — same
    shape as `graph/runner.py`'s `upsert_run_status`, not reused directly
    from there to avoid a circular import (`runner.py` already imports
    `build_master_graph` from this module).
    """
    summary = await session.get(CashflowSummary, thread_id)
    if summary is None:
        summary = CashflowSummary(thread_id=thread_id)
        session.add(summary)

    summary.statement_id = result["statement_id"]
    summary.weekly = result["weekly"]
    summary.rolling_month = result["rolling_month"]
    summary.fixed_costs_status = result["fixed_costs_status"]
    await session.flush()
    return summary


async def _cashflow_calculation_node(
    _state: MasterGraphState, config: RunnableConfig
) -> dict:
    """Real cashflow_calculation subgraph, wired in place of the
    placeholder. No Drive client needed, no interrupt() — same reasoning as
    `_fixed_costs_reconciliation_node`, wired directly rather than waiting
    for the master-graph checkpointer (PLAN.md step 12).

    Unlike the other subgraph wrappers, this one's result is captured and
    persisted (`_upsert_cashflow_summary`) rather than discarded — the
    subgraph itself is stateless/self-selecting ("current statement" from
    the DB, see `subgraphs/cashflow/nodes.py`), so without this the
    computed `CashflowState` would vanish the instant this node returns.
    """
    thread_id = config["configurable"]["thread_id"]

    async with async_session_factory() as session:
        try:
            cashflow_graph = build_cashflow_graph(session=session)
            result = await cashflow_graph.ainvoke(
                {
                    "statement_id": None,
                    "transactions": [],
                    "weekly": None,
                    "fixed_costs_status": [],
                    "rolling_month": None,
                }
            )
            await _upsert_cashflow_summary(thread_id, result, session=session)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [CASHFLOW_CALCULATION]}


async def _investment_analysis_node(_state: MasterGraphState) -> dict:
    """Real investment_analysis subgraph, wired in place of the placeholder.
    No interrupt() here either — wired now like the other non-HITL steps.
    """
    async with async_session_factory() as session:
        try:
            chat_model = build_investment_model()
            investment_graph = build_investment_graph(
                session=session, chat_model=chat_model
            )
            await investment_graph.ainvoke(
                {
                    "statement_id": None,
                    "surplus": None,
                    "safety_buffer": None,
                    "trend": None,
                    "proposal": None,
                }
            )
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [INVESTMENT_ANALYSIS]}


async def _reporting_node(_state: MasterGraphState) -> dict:
    """Real reporting subgraph, wired in place of the placeholder. No
    interrupt() here either — wired now like the other non-HITL steps.
    """
    async with async_session_factory() as session:
        try:
            reporting_graph = build_reporting_graph(session=session)
            await reporting_graph.ainvoke(
                {
                    "statement_id": None,
                    "generate_monthly": False,
                    "cashflow": None,
                    "needs_review_items": [],
                    "investment_recommendation": None,
                    "monthly_comparison": None,
                    "weekly_html": None,
                    "monthly_html": None,
                }
            )
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [REPORTING]}


async def _email_delivery_node(_state: MasterGraphState) -> dict:
    """Real email_delivery subgraph, wired in place of the placeholder.
    Delivers the REPORTS `pending` queue — no interrupt() here either,
    wired now like the other non-HITL steps.
    """
    async with async_session_factory() as session:
        try:
            smtp_client = build_smtp_client(settings)
            email_delivery_graph = build_email_delivery_graph(
                session=session,
                smtp_client=smtp_client,
                from_address=settings.smtp_user,
                to_address=settings.report_recipient_email,
            )
            await email_delivery_graph.ainvoke({"pending": [], "results": []})
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return {"visited": [EMAIL_DELIVERY]}


def _build_alert_message(
    alert_details: list[dict], *, from_address: str, to_address: str
) -> EmailMessage:
    """Pure message-building logic, factored out of `_alert_immediate_node`
    so it's directly unit-testable without needing a real/fake SMTP client
    or `Settings` — `_alert_immediate_node` itself stays untested glue code,
    same as every other master-graph wrapper's `build_x_client(settings)`
    call (the real logic lives in a subgraph elsewhere; here, in this pure
    function).
    """
    details = "\n".join(
        f"- Wyciąg {detail['statement_id']}: {detail['failure_reason']}"
        for detail in alert_details
    )

    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = "Finance Agent — błąd weryfikacji wyciągu"
    message.set_content(
        "Wykryto błąd podczas weryfikacji wyciągu bankowego:\n\n" + details
    )
    return message


async def _alert_immediate_node(state: MasterGraphState) -> dict:
    """Real alert_immediate, wired in place of the placeholder. Not a
    subgraph — docs/11's diagram draws it as a single master-graph node
    (`ALERT[[alert_immediate]]`), not a nested StateGraph, since it's just
    "build one short message, send it". No DB session — nothing is
    persisted for immediate alerts (unlike weekly/monthly reports).
    """
    smtp_client = build_smtp_client(settings)
    message = _build_alert_message(
        state["alert_details"],
        from_address=settings.smtp_user,
        to_address=settings.report_recipient_email,
    )
    await smtp_client.send(message)

    return {"visited": [ALERT_IMMEDIATE]}


def _route_after_verification_pre_check(
    state: MasterGraphState,
) -> Literal["extraction", "alert_immediate"]:
    return EXTRACTION if state["verification_ok"] else ALERT_IMMEDIATE


def _route_after_verification_post_check(
    state: MasterGraphState,
) -> Literal["categorization", "alert_immediate"]:
    return CATEGORIZATION if state["verification_ok"] else ALERT_IMMEDIATE


def build_master_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    ingestion_node: Callable[[MasterGraphState], Awaitable[dict]] = _ingestion_node,
    verification_pre_check_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _verification_pre_check_node,
    extraction_node: Callable[[MasterGraphState], Awaitable[dict]] = _extraction_node,
    verification_post_check_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _verification_post_check_node,
    categorization_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _categorization_node,
    fixed_costs_reconciliation_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _fixed_costs_reconciliation_node,
    cashflow_calculation_node: Callable[
        [MasterGraphState, RunnableConfig], Awaitable[dict]
    ] = _cashflow_calculation_node,
    investment_analysis_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _investment_analysis_node,
    reporting_node: Callable[[MasterGraphState], Awaitable[dict]] = _reporting_node,
    email_delivery_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _email_delivery_node,
    alert_immediate_node: Callable[
        [MasterGraphState], Awaitable[dict]
    ] = _alert_immediate_node,
) -> CompiledStateGraph:
    """Build the master orchestration graph per docs/11-spec-orchestration-scheduling.md.

    Every step is now wired for real, including `categorization` (PLAN.md
    step 12 — see `_categorization_node`'s docstring for how its
    `interrupt()` correctly pauses this whole graph despite not being
    mounted via a literal `add_node(name, compiled_subgraph)`). Only
    `categorization` needs `checkpointer` to actually be a real, persistent
    saver for its pause/resume to survive a process restart — every other
    node has no human-in-the-loop, so `checkpointer=None` (the default,
    used by every existing test that doesn't need interrupts) is fine for
    them.

    `ingestion_node`/`verification_pre_check_node`/`extraction_node`/
    `verification_post_check_node`/`categorization_node`/
    `fixed_costs_reconciliation_node`/`cashflow_calculation_node`/
    `investment_analysis_node`/`reporting_node`/`email_delivery_node`/
    `alert_immediate_node` default to the real subgraph wrappers (async —
    require `graph.ainvoke(...)`, not `.invoke()`); tests that only care
    about branching logic can override them with cheap sync placeholders to
    stay hermetic and invocable via sync `.invoke()`.
    """
    builder = StateGraph(MasterGraphState)

    builder.add_node(INGESTION, ingestion_node)
    builder.add_node(VERIFICATION_PRE_CHECK, verification_pre_check_node)
    builder.add_node(EXTRACTION, extraction_node)
    builder.add_node(VERIFICATION_POST_CHECK, verification_post_check_node)
    builder.add_node(CATEGORIZATION, categorization_node)
    builder.add_node(FIXED_COSTS_RECONCILIATION, fixed_costs_reconciliation_node)
    builder.add_node(CASHFLOW_CALCULATION, cashflow_calculation_node)
    builder.add_node(INVESTMENT_ANALYSIS, investment_analysis_node)
    builder.add_node(REPORTING, reporting_node)
    builder.add_node(EMAIL_DELIVERY, email_delivery_node)
    builder.add_node(ALERT_IMMEDIATE, alert_immediate_node)

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
    # Unconditional: categorization's own human_review (interrupt()) already
    # resolves everything it can internally; items left needs_review after
    # resume still flow through — step 8 already decided they're included in
    # cashflow totals with a warning, not blocked on.
    builder.add_edge(CATEGORIZATION, FIXED_COSTS_RECONCILIATION)
    builder.add_edge(FIXED_COSTS_RECONCILIATION, CASHFLOW_CALCULATION)
    builder.add_edge(CASHFLOW_CALCULATION, INVESTMENT_ANALYSIS)
    builder.add_edge(INVESTMENT_ANALYSIS, REPORTING)
    builder.add_edge(REPORTING, EMAIL_DELIVERY)
    builder.add_edge(EMAIL_DELIVERY, END)
    builder.add_edge(ALERT_IMMEDIATE, END)

    return builder.compile(checkpointer=checkpointer)
