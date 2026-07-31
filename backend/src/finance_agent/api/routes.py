"""API routes for the backend (docs/13-spec-backend-api.md). One route per
row in that spec's endpoint table, plus `GET /categories` (not in the
table, but already consumed by the frontend's `ApiClient.getCategories()`
— without it, Review Queue has nothing to build a category dropdown
against).
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.api.dependencies import (
    get_checkpointer,
    get_db_session,
    get_run_trigger,
    require_api_key,
)
from finance_agent.api.schemas import CashflowSummary as CashflowSummarySchema
from finance_agent.api.schemas import Category as CategorySchema
from finance_agent.api.schemas import (
    GraphEdge,
    GraphNode,
    GraphStructureResponse,
    HealthResponse,
    PendingReview,
    ResumeRequest,
    RunHistoryEntry,
    RunState,
    RunSummary,
)
from finance_agent.config import settings
from finance_agent.db.models import CashflowSummary as CashflowSummaryModel
from finance_agent.db.models import Category, Run
from finance_agent.graph.master import (
    ALERT_IMMEDIATE,
    CATEGORIZATION,
    build_master_graph,
)
from finance_agent.graph.runner import upsert_run_status

router = APIRouter(dependencies=[Depends(require_api_key)])

# Visual hint for the frontend's graph view (docs/11's mermaid used to draw
# these as special shapes: `[[alert]]`, `{{interrupt}}`) — `categorization`
# contains `human_review`'s `interrupt()` internally (PLAN.md step 12), not
# a separate master-graph node, so it's the one marked here.
_NODE_KIND_BY_NAME = {
    CATEGORIZATION: "interrupt",
    ALERT_IMMEDIATE: "alert",
}


@router.get("/graph/structure", response_model=GraphStructureResponse)
async def get_graph_structure() -> GraphStructureResponse:
    """No checkpointer needed — this is the static graph shape, verified
    directly against a real `build_master_graph()` call
    (`Node(id, name, data, metadata)` / `Edge(source, target, data,
    conditional)`) before relying on those field names.
    """
    graph = build_master_graph()
    drawable = graph.get_graph()

    nodes = [
        GraphNode(id=node.id, label=node.name, kind=_NODE_KIND_BY_NAME.get(node.id))
        for node in drawable.nodes.values()
    ]
    edges = [
        GraphEdge(
            id=f"{edge.source}-{edge.target}", source=edge.source, target=edge.target
        )
        for edge in drawable.edges
    ]
    return GraphStructureResponse(
        mermaid=drawable.draw_mermaid(), nodes=nodes, edges=edges
    )


@router.get("/categories", response_model=list[CategorySchema])
async def list_categories(
    session: AsyncSession = Depends(get_db_session),
) -> list[CategorySchema]:
    categories = (await session.execute(select(Category))).scalars().all()
    return [
        CategorySchema(id=str(c.id), name=c.name, score=c.score, type=c.type)
        for c in categories
    ]


@router.post("/runs", response_model=RunSummary, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    trigger: Callable[..., Awaitable[dict]] = Depends(get_run_trigger),
) -> RunSummary:
    """Manual "run now" trigger — a fresh `thread_id`, distinct from the
    weekly cron thread (`generate_weekly_thread_id`, `graph/runner.py`),
    same as the frontend's mock (`manual-${Date.now()}`). The `RUNS` row is
    written synchronously so `GET /runs` reflects it immediately; the
    actual pipeline run happens in the background so this request returns
    right away instead of blocking for the whole pipeline.
    """
    thread_id = f"manual-{uuid.uuid4()}"
    run = await upsert_run_status(thread_id, "running", session=session)
    await session.commit()

    background_tasks.add_task(trigger, thread_id)

    return RunSummary(
        thread_id=run.thread_id,
        status=run.status,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    session: AsyncSession = Depends(get_db_session),
) -> list[RunSummary]:
    runs = (
        (await session.execute(select(Run).order_by(Run.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        RunSummary(
            thread_id=r.thread_id,
            status=r.status,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in runs
    ]


def _pending_reviews_from_snapshot(snapshot: Any) -> list[PendingReview]:
    """Decodes categorization's `human_review` interrupt payload
    (`{"pending_reviews": [...]}`, `subgraphs/categorization/nodes.py`).
    Only interrupt shape defined today — reconcile if other subgraphs add
    their own `interrupt()` later (same note as the frontend's own types).
    """
    pending: list[PendingReview] = []
    for interrupt in snapshot.interrupts:
        value = interrupt.value
        if isinstance(value, dict) and "pending_reviews" in value:
            pending.extend(
                PendingReview(
                    transaction_id=item["transaction_id"],
                    description=item["description"],
                    counterparty=item.get("counterparty"),
                    amount=item["amount"],
                    suggested_category=item.get("suggested_category"),
                    suggested_confidence=item.get("suggested_confidence"),
                )
                for item in value["pending_reviews"]
            )
    return pending


@router.get("/runs/{thread_id}/state", response_model=RunState)
async def get_run_state(
    thread_id: str,
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
) -> RunState:
    graph = build_master_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})

    # Verified directly: an unknown thread_id yields values={}, created_at=None.
    if snapshot.created_at is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown thread_id: {thread_id}"
        )

    return RunState(
        values=snapshot.values,
        pending_reviews=_pending_reviews_from_snapshot(snapshot),
    )


@router.get("/runs/{thread_id}/history", response_model=list[RunHistoryEntry])
async def get_run_history(
    thread_id: str,
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
) -> list[RunHistoryEntry]:
    graph = build_master_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    history = [
        RunHistoryEntry(
            checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
            step=(snapshot.metadata or {}).get("step", 0),
            values=snapshot.values,
            next=list(snapshot.next),
            created_at=snapshot.created_at or "",
        )
        async for snapshot in graph.aget_state_history(config)
    ]

    if not history:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown thread_id: {thread_id}"
        )

    return history


@router.post("/runs/{thread_id}/resume", response_model=RunState)
async def resume_run(
    thread_id: str,
    body: ResumeRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
    trigger: Callable[..., Awaitable[dict]] = Depends(get_run_trigger),
) -> RunState:
    run = await session.get(Run, thread_id)
    if run is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown thread_id: {thread_id}"
        )

    run.status = "running"
    await session.commit()

    background_tasks.add_task(trigger, thread_id, resume=body.resume)

    # Eventual consistency: the background task hasn't necessarily
    # progressed yet — this reflects state as of right now (same shape as
    # GET .../state), the frontend can poll that endpoint again for updates.
    graph = build_master_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    return RunState(
        values=snapshot.values,
        pending_reviews=_pending_reviews_from_snapshot(snapshot),
    )


@router.get("/runs/{thread_id}/cashflow", response_model=CashflowSummarySchema)
async def get_run_cashflow(
    thread_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CashflowSummarySchema:
    """Reads the `cashflow_calculation` subgraph's persisted output
    (`CashflowSummary`, `db/models.py`) — the subgraph itself is stateless
    per invocation, so this table is the only place its result survives past
    the master graph moving on to the next node.
    """
    summary = await session.get(CashflowSummaryModel, thread_id)
    if summary is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown thread_id: {thread_id}"
        )

    return CashflowSummarySchema(
        statement_id=summary.statement_id,
        weekly=summary.weekly,
        rolling_month=summary.rolling_month,
        fixed_costs_status=summary.fixed_costs_status,
    )


@router.delete("/runs/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    thread_id: str,
    session: AsyncSession = Depends(get_db_session),
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
) -> None:
    """Deletes a run and its checkpoint history. `cashflow_summaries` rows
    cascade automatically (`ondelete="CASCADE"`, `db/models.py`). A run
    still `running` is refused — `BackgroundTasks` may still be writing to
    it, and deleting the `runs` row mid-write would break the FK that
    `cashflow_summaries` depends on.
    """
    run = await session.get(Run, thread_id)
    if run is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown thread_id: {thread_id}"
        )
    if run.status == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot delete run in progress: {thread_id}",
        )

    await checkpointer.adelete_thread(thread_id)
    await session.delete(run)
    await session.commit()


@router.get("/health", response_model=HealthResponse)
async def get_health(
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
        database_ok = True
    except Exception:  # noqa: BLE001 -- any DB failure means "down", not a 500
        database_ok = False

    # Field stays named `ollama` in the wire contract (frontend's
    # HealthResponse) even though this project uses OVH AI Endpoints, not
    # Ollama, since docs/12 — renaming the JSON field would break the
    # already-built frontend for no functional benefit.
    ovh_ok = False
    if settings.ovh_ai_endpoints_base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.ovh_ai_endpoints_base_url}/models"
                )
                ovh_ok = response.status_code == 200
        except Exception:  # noqa: BLE001 -- any network failure means "down"
            ovh_ok = False

    if database_ok and ovh_ok:
        overall = "ok"
    elif database_ok or ovh_ok:
        overall = "degraded"
    else:
        overall = "down"

    return HealthResponse(status=overall, database=database_ok, ollama=ovh_ok)
