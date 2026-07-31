"""Trigger entry point for the master graph
(docs/11-spec-orchestration-scheduling.md's "logika wyzwalania"). The actual
HTTP wrapper (`POST /runs`, `POST /runs/{thread_id}/resume`) is
`finance_agent.api` (PLAN.md step 13), which calls this module rather than
duplicating any of it.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from finance_agent.db.models import Run
from finance_agent.db.session import async_session_factory
from finance_agent.graph.checkpointer import build_checkpointer
from finance_agent.graph.master import build_master_graph

INITIAL_MASTER_STATE = {
    "verification_ok": True,
    "alert_details": [],
    "visited": [],
}


def generate_weekly_thread_id(*, today: date | None = None) -> str:
    """One thread per ISO calendar week (docs/11: "jeden wątek per tydzień"),
    e.g. `run-2026-W05`.
    """
    iso_year, iso_week, _iso_weekday = (today or datetime.now(UTC).date()).isocalendar()
    return f"run-{iso_year}-W{iso_week:02d}"


async def upsert_run_status(
    thread_id: str, status: str, *, session: AsyncSession
) -> Run:
    """Upsert into `RUNS` (docs/13-spec-backend-api.md) — deliberately
    separate from the checkpointer's own tables (see `Run`'s docstring):
    the checkpointer can't answer "list all thread_ids" or represent
    `failed` (an unhandled exception never produces a checkpoint), both
    needed by `GET /runs`. Shared by `run_master_graph` (status transitions
    around an invocation) and `finance_agent.api.routes` (`POST /runs`
    creates the initial `"running"` row) so the upsert logic exists once.
    """
    run = await session.get(Run, thread_id)
    if run is None:
        run = Run(thread_id=thread_id, status=status)
        session.add(run)
    else:
        run.status = status
    await session.flush()
    return run


async def run_master_graph(
    thread_id: str,
    *,
    resume: dict | None = None,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    checkpointer_factory: Callable[
        [], AbstractAsyncContextManager
    ] = build_checkpointer,
    graph_factory: Callable[..., CompiledStateGraph] = build_master_graph,
) -> dict:
    """Runs (or resumes) one master-graph invocation under `thread_id`.

    Opens a fresh `AsyncPostgresSaver` (and, via each real node, a fresh DB
    session) for exactly this call — nothing is held open across an
    `interrupt()` pause (see `_categorization_node`'s docstring in
    `graph/master.py`). Calling this again later with `resume=` set is a
    completely separate call that picks up from the persisted checkpoint.

    Tracks `RUNS.status` around the invocation: `"running"` before
    `ainvoke`, `"failed"` (then re-raised) if it raises, otherwise
    `"waiting_for_review"` if the result paused on `interrupt()` or
    `"completed"` if it ran to `END`.

    `session_factory`/`checkpointer_factory`/`graph_factory` default to the
    real dev-DB-backed implementations; tests inject fakes (a test-DB
    sessionmaker, an `InMemorySaver`-backed checkpointer, a master graph
    wired with placeholders) to exercise this status-tracking logic without
    touching the dev database or requiring real Drive/OVH/SMTP config.
    """
    async with session_factory() as session:
        await upsert_run_status(thread_id, "running", session=session)
        await session.commit()

    async with checkpointer_factory() as checkpointer:
        graph = graph_factory(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            if resume is not None:
                result = await graph.ainvoke(Command(resume=resume), config)
            else:
                result = await graph.ainvoke(INITIAL_MASTER_STATE, config)
        except Exception:
            async with session_factory() as session:
                await upsert_run_status(thread_id, "failed", session=session)
                await session.commit()
            raise

    status = "waiting_for_review" if "__interrupt__" in result else "completed"
    async with session_factory() as session:
        await upsert_run_status(thread_id, status, session=session)
        await session.commit()

    return result
