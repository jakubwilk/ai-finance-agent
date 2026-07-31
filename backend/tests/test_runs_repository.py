"""Tests `RUNS` status tracking (docs/13-spec-backend-api.md) —
`upsert_run_status` directly, and `run_master_graph`'s status transitions
around a full invocation. The latter uses injected `session_factory`/
`checkpointer_factory`/`graph_factory` (PLAN.md step 13's DI addition to
`graph/runner.py`) so it never touches the dev database, a real Postgres
checkpointer, or real Drive/OVH/SMTP config — only the master graph's
routing/status-tracking logic is under test here, not any subgraph's own
business logic (each already has its own dedicated test file).
"""

from contextlib import asynccontextmanager

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from finance_agent.config import settings
from finance_agent.db.models import Run
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
from finance_agent.graph.runner import run_master_graph, upsert_run_status


@pytest.fixture
async def session_factory():
    """Same SAVEPOINT-per-test isolation as `conftest.py`'s `db_session`,
    but exposed as a zero-arg factory — `run_master_graph` calls it
    multiple times per invocation (once per status transition), all
    sharing one connection/transaction so they see each other's writes and
    everything rolls back at the end.
    """
    engine = create_async_engine(settings.test_database_url)
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()

        def _factory() -> AsyncSession:
            return AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

        yield _factory
        await outer_transaction.rollback()
    await engine.dispose()


def _make_checkpointer_factory():
    """A shared `InMemorySaver` instance behind an async-context-manager
    factory — resume tests need the *same* saver across two
    `run_master_graph` calls (initial + resume) to see the paused state.
    """
    saver = InMemorySaver()

    @asynccontextmanager
    async def _factory():
        yield saver

    return _factory


def _placeholder_kwargs(**overrides):
    kwargs = {
        "ingestion_node": _make_placeholder(INGESTION),
        "verification_pre_check_node": _make_placeholder(VERIFICATION_PRE_CHECK),
        "extraction_node": _make_placeholder(EXTRACTION),
        "verification_post_check_node": _make_placeholder(VERIFICATION_POST_CHECK),
        "categorization_node": _make_placeholder(CATEGORIZATION),
        "fixed_costs_reconciliation_node": _make_placeholder(
            FIXED_COSTS_RECONCILIATION
        ),
        "cashflow_calculation_node": _make_placeholder(CASHFLOW_CALCULATION),
        "investment_analysis_node": _make_placeholder(INVESTMENT_ANALYSIS),
        "reporting_node": _make_placeholder(REPORTING),
        "email_delivery_node": _make_placeholder(EMAIL_DELIVERY),
        "alert_immediate_node": _make_placeholder(ALERT_IMMEDIATE),
    }
    kwargs.update(overrides)
    return kwargs


def _completing_graph_factory(*, checkpointer):
    return build_master_graph(checkpointer=checkpointer, **_placeholder_kwargs())


def _failing_graph_factory(*, checkpointer):
    async def _raise(_state):
        raise RuntimeError("boom")

    return build_master_graph(
        checkpointer=checkpointer, **_placeholder_kwargs(ingestion_node=_raise)
    )


async def _interrupting_categorization(_state):
    interrupt({"pending_reviews": []})
    return {"visited": [CATEGORIZATION]}


def _interrupting_graph_factory(*, checkpointer):
    return build_master_graph(
        checkpointer=checkpointer,
        **_placeholder_kwargs(categorization_node=_interrupting_categorization),
    )


async def test_upsert_run_status_creates_then_updates(db_session):
    created = await upsert_run_status("thread-x", "running", session=db_session)
    assert created.status == "running"

    updated = await upsert_run_status("thread-x", "completed", session=db_session)
    assert updated.thread_id == "thread-x"
    assert updated.status == "completed"

    all_runs = (await db_session.execute(select(Run))).scalars().all()
    assert len(all_runs) == 1


async def test_run_master_graph_marks_completed_on_success(session_factory):
    result = await run_master_graph(
        "test-completed",
        session_factory=session_factory,
        checkpointer_factory=_make_checkpointer_factory(),
        graph_factory=_completing_graph_factory,
    )

    assert "__interrupt__" not in result
    async with session_factory() as session:
        run = await session.get(Run, "test-completed")
        assert run.status == "completed"


async def test_run_master_graph_marks_failed_on_exception(session_factory):
    with pytest.raises(RuntimeError, match="boom"):
        await run_master_graph(
            "test-failed",
            session_factory=session_factory,
            checkpointer_factory=_make_checkpointer_factory(),
            graph_factory=_failing_graph_factory,
        )

    async with session_factory() as session:
        run = await session.get(Run, "test-failed")
        assert run.status == "failed"


async def test_run_master_graph_marks_waiting_for_review_on_interrupt(session_factory):
    result = await run_master_graph(
        "test-waiting",
        session_factory=session_factory,
        checkpointer_factory=_make_checkpointer_factory(),
        graph_factory=_interrupting_graph_factory,
    )

    assert "__interrupt__" in result
    async with session_factory() as session:
        run = await session.get(Run, "test-waiting")
        assert run.status == "waiting_for_review"


async def test_run_master_graph_resume_completes_after_review(session_factory):
    checkpointer_factory = _make_checkpointer_factory()

    await run_master_graph(
        "test-resume",
        session_factory=session_factory,
        checkpointer_factory=checkpointer_factory,
        graph_factory=_interrupting_graph_factory,
    )

    result = await run_master_graph(
        "test-resume",
        resume="approved",
        session_factory=session_factory,
        checkpointer_factory=checkpointer_factory,
        graph_factory=_interrupting_graph_factory,
    )

    assert "__interrupt__" not in result
    async with session_factory() as session:
        run = await session.get(Run, "test-resume")
        assert run.status == "completed"
