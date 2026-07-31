"""Tests the FastAPI backend (docs/13-spec-backend-api.md) end to end at
the HTTP layer, via `httpx.AsyncClient` + `ASGITransport` (consistent with
the rest of this suite's async style — no `TestClient`/sync wrapper).

`get_db_session`/`get_checkpointer`/`get_run_trigger` are overridden
(`app.dependency_overrides`) to point at `TEST_DATABASE_URL` and an
`InMemorySaver`, and to a fake trigger that updates `RUNS` without running
the real pipeline — the DI seam this whole step exists to add (PLAN.md
step 12's testing gap). `require_api_key` is tested separately, with real
settings, since it's the one dependency that must NOT be faked.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from finance_agent.api.app import create_app
from finance_agent.api.dependencies import (
    get_checkpointer,
    get_db_session,
    get_run_trigger,
    require_api_key,
)
from finance_agent.config import settings
from finance_agent.db.models import CashflowSummary, Category, Run
from finance_agent.graph.runner import upsert_run_status


@pytest.fixture
async def api_client():
    engine = create_async_engine(settings.test_database_url)
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()

        def session_factory() -> AsyncSession:
            return AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

        async def _override_get_db_session():
            session = session_factory()
            try:
                yield session
            finally:
                await session.close()

        checkpointer = InMemorySaver()

        async def _override_get_checkpointer():
            yield checkpointer

        trigger_calls: list[tuple[str, object]] = []

        async def _fake_trigger(thread_id: str, *, resume=None) -> dict:
            trigger_calls.append((thread_id, resume))
            async with session_factory() as session:
                await upsert_run_status(thread_id, "completed", session=session)
                await session.commit()
            return {"visited": []}

        app = create_app()
        app.dependency_overrides[get_db_session] = _override_get_db_session
        app.dependency_overrides[get_checkpointer] = _override_get_checkpointer
        app.dependency_overrides[get_run_trigger] = lambda: _fake_trigger
        app.dependency_overrides[require_api_key] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.session_factory = session_factory  # type: ignore[attr-defined]
            client.trigger_calls = trigger_calls  # type: ignore[attr-defined]
            client.checkpointer = checkpointer  # type: ignore[attr-defined]
            yield client

        await outer_transaction.rollback()
    await engine.dispose()


async def test_get_graph_structure(api_client):
    response = await api_client.get("/graph/structure")

    assert response.status_code == 200
    body = response.json()
    assert body["mermaid"]
    categorization = next(n for n in body["nodes"] if n["id"] == "categorization")
    assert categorization["kind"] == "interrupt"
    alert = next(n for n in body["nodes"] if n["id"] == "alert_immediate")
    assert alert["kind"] == "alert"
    assert any(e["source"] == "ingestion" for e in body["edges"])


async def test_get_categories_returns_seeded_rows(api_client):
    async with api_client.session_factory() as session:
        session.add(Category(name="Jedzenie", score=80, type="expense"))
        await session.commit()

    response = await api_client.get("/categories")

    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "Jedzenie" in names


async def test_trigger_run_is_immediately_listed(api_client):
    response = await api_client.post("/runs")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "running"
    thread_id = body["threadId"]

    list_response = await api_client.get("/runs")
    thread_ids = [r["threadId"] for r in list_response.json()]
    assert thread_id in thread_ids
    assert api_client.trigger_calls == [(thread_id, None)]


async def test_get_run_state_unknown_thread_returns_404(api_client):
    response = await api_client.get("/runs/does-not-exist/state")

    assert response.status_code == 404


async def test_get_run_history_unknown_thread_returns_404(api_client):
    response = await api_client.get("/runs/does-not-exist/history")

    assert response.status_code == 404


async def test_get_run_cashflow_unknown_thread_returns_404(api_client):
    response = await api_client.get("/runs/does-not-exist/cashflow")

    assert response.status_code == 404


async def test_get_run_cashflow_returns_persisted_summary(api_client):
    async with api_client.session_factory() as session:
        await upsert_run_status("test-cashflow", "completed", session=session)
        session.add(
            CashflowSummary(
                thread_id="test-cashflow",
                statement_id="11111111-1111-1111-1111-111111111111",
                weekly={
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-07",
                    "total_income": "1000.00",
                    "total_expense": "-400.00",
                    "category_breakdown": [
                        {
                            "category_id": None,
                            "category_name": "Nieskategoryzowane",
                            "total": "-400.00",
                        }
                    ],
                    "needs_review_count": 0,
                    "surplus": "600.00",
                },
                rolling_month=None,
                fixed_costs_status=[
                    {
                        "fixed_cost_id": "fc-1",
                        "fixed_cost_name": "Czynsz",
                        "expected_amount": "1500.00",
                        "actual_amount": "1500.00",
                        "status": "matched",
                    }
                ],
            )
        )
        await session.commit()

    response = await api_client.get("/runs/test-cashflow/cashflow")

    assert response.status_code == 200
    body = response.json()
    assert body["statementId"] == "11111111-1111-1111-1111-111111111111"
    assert body["weekly"]["periodStart"] == "2026-01-01"
    assert (
        body["weekly"]["categoryBreakdown"][0]["categoryName"] == "Nieskategoryzowane"
    )
    assert body["rollingMonth"] is None
    assert body["fixedCostsStatus"][0]["fixedCostId"] == "fc-1"


async def test_delete_run_unknown_thread_returns_404(api_client):
    response = await api_client.delete("/runs/does-not-exist")

    assert response.status_code == 404


async def test_delete_run_running_returns_409(api_client):
    async with api_client.session_factory() as session:
        await upsert_run_status("test-delete-running", "running", session=session)
        await session.commit()

    response = await api_client.delete("/runs/test-delete-running")

    assert response.status_code == 409
    async with api_client.session_factory() as session:
        run = await session.get(Run, "test-delete-running")
        assert run is not None


async def test_delete_run_removes_run_and_cascades_cashflow_summary(
    api_client, monkeypatch
):
    async with api_client.session_factory() as session:
        await upsert_run_status("test-delete-completed", "completed", session=session)
        session.add(
            CashflowSummary(thread_id="test-delete-completed", fixed_costs_status=[])
        )
        await session.commit()

    deleted_thread_ids: list[str] = []
    original_adelete_thread = api_client.checkpointer.adelete_thread

    async def _spy_adelete_thread(thread_id: str) -> None:
        deleted_thread_ids.append(thread_id)
        await original_adelete_thread(thread_id)

    monkeypatch.setattr(api_client.checkpointer, "adelete_thread", _spy_adelete_thread)

    response = await api_client.delete("/runs/test-delete-completed")

    assert response.status_code == 204
    assert deleted_thread_ids == ["test-delete-completed"]
    async with api_client.session_factory() as session:
        assert await session.get(Run, "test-delete-completed") is None
        assert await session.get(CashflowSummary, "test-delete-completed") is None


async def test_resume_run_unknown_thread_returns_404(api_client):
    response = await api_client.post(
        "/runs/does-not-exist/resume", json={"resume": {"decisions": {}}}
    )

    assert response.status_code == 404


async def test_resume_run_updates_status_and_returns_state_shape(api_client):
    async with api_client.session_factory() as session:
        await upsert_run_status("test-thread", "waiting_for_review", session=session)
        await session.commit()

    response = await api_client.post(
        "/runs/test-thread/resume",
        json={"resume": {"decisions": {"txn-1": "Jedzenie"}}},
    )

    assert response.status_code == 200
    body = response.json()
    assert "values" in body
    assert "pendingReviews" in body
    assert api_client.trigger_calls == [
        ("test-thread", {"decisions": {"txn-1": "Jedzenie"}})
    ]

    list_response = await api_client.get("/runs")
    status_by_thread = {r["threadId"]: r["status"] for r in list_response.json()}
    assert status_by_thread["test-thread"] == "completed"


async def test_health_reports_database_reachable(api_client):
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database"] is True
    assert "ollama" in body
    assert body["status"] in {"ok", "degraded", "down"}


@pytest.fixture
async def api_client_with_real_auth(monkeypatch):
    """Only `require_api_key` is real here — everything else is overridden
    the same way as `api_client`, so a 401 is the only thing being tested,
    not accidentally a 500 from touching the dev DB/checkpointer.
    """
    monkeypatch.setattr(settings, "backend_api_key", "test-secret-key")

    engine = create_async_engine(settings.test_database_url)
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()

        def session_factory() -> AsyncSession:
            return AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

        async def _override_get_db_session():
            session = session_factory()
            try:
                yield session
            finally:
                await session.close()

        app = create_app()
        app.dependency_overrides[get_db_session] = _override_get_db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        await outer_transaction.rollback()
    await engine.dispose()


async def test_missing_api_key_returns_401(api_client_with_real_auth):
    response = await api_client_with_real_auth.get("/health")

    assert response.status_code == 401


async def test_wrong_api_key_returns_401(api_client_with_real_auth):
    response = await api_client_with_real_auth.get(
        "/health", headers={"X-API-Key": "wrong-key"}
    )

    assert response.status_code == 401


async def test_correct_api_key_is_accepted(api_client_with_real_auth):
    response = await api_client_with_real_auth.get(
        "/health", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
