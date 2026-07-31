"""Pydantic response/request models for the backend API
(docs/13-spec-backend-api.md). Field names mirror
`frontend/src/modules/common/models/api.ts` exactly — that contract already
exists (built against a mock, Plan B step 1) and this backend must match it,
not redesign it. `CamelModel` serializes every field as camelCase JSON
(FastAPI's `response_model_by_alias` defaults to `True`, verified against
the installed version), matching the frontend's TypeScript field names
while keeping idiomatic snake_case in Python.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunSummary(CamelModel):
    thread_id: str
    status: str  # "running" | "completed" | "failed" | "waiting_for_review"
    created_at: str
    updated_at: str


class Category(CamelModel):
    id: str
    name: str
    score: int
    type: str  # "income" | "expense" | "transfer"


class PendingReview(CamelModel):
    """One entry of categorization's `human_review` interrupt payload
    (`subgraphs/categorization/nodes.py`'s `make_human_review`).
    """

    transaction_id: str
    description: str
    counterparty: str | None
    amount: str
    suggested_category: str | None
    suggested_confidence: float | None


class RunState(CamelModel):
    values: dict[str, Any]
    pending_reviews: list[PendingReview]


class RunHistoryEntry(CamelModel):
    checkpoint_id: str
    step: int
    values: dict[str, Any]
    next: list[str]
    created_at: str


class GraphNode(CamelModel):
    id: str
    label: str
    kind: str | None = None  # "default" | "interrupt" | "alert"


class GraphEdge(CamelModel):
    id: str
    source: str
    target: str
    label: str | None = None


class GraphStructureResponse(CamelModel):
    mermaid: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class CategoryBreakdownEntry(CamelModel):
    """One entry of `PeriodSummary.category_breakdown`
    (`subgraphs/cashflow/state.py`'s `CategoryBreakdownEntry`). `total` is
    signed — positive for income categories, negative for expense
    categories, since every transaction in the period is grouped, not just
    expenses. `category_id=None` means "Nieskategoryzowane" (uncategorized).
    """

    category_id: str | None
    category_name: str
    total: str


class FixedCostStatusEntry(CamelModel):
    """Reconciliation status for one `FIXED_COSTS` row against the current
    statement's transactions (`subgraphs/cashflow/state.py`'s
    `FixedCostStatusEntry`).
    """

    fixed_cost_id: str
    fixed_cost_name: str
    expected_amount: str
    actual_amount: str | None
    status: str  # "matched" | "amount_changed" | "missing_payment"


class PeriodSummary(CamelModel):
    """One period's aggregation (`subgraphs/cashflow/state.py`'s
    `PeriodSummary`). `total_expense`/`surplus` are signed decimal strings
    (expense negative).
    """

    period_start: str
    period_end: str
    total_income: str
    total_expense: str
    category_breakdown: list[CategoryBreakdownEntry]
    needs_review_count: int
    surplus: str


class CashflowSummary(CamelModel):
    """Output of the `cashflow_calculation` subgraph
    (`subgraphs/cashflow/state.py`'s `CashflowState`), persisted per
    `thread_id` in `CashflowSummary` (`db/models.py`) since the subgraph
    itself is stateless per invocation. `weekly` covers the current
    statement's own period; `rolling_month` covers the calendar month to
    date across every processed statement in it. Either can be `None` if no
    statement had been processed yet when this thread's run computed it.
    """

    statement_id: str | None
    weekly: PeriodSummary | None
    rolling_month: PeriodSummary | None
    fixed_costs_status: list[FixedCostStatusEntry]


class HealthResponse(CamelModel):
    status: str  # "ok" | "degraded" | "down"
    database: bool
    ollama: bool


class ResumeRequest(BaseModel):
    """POST /runs/{thread_id}/resume body — `resume` maps directly to
    `Command(resume=...)`; its shape is node-specific (whatever the
    interrupted node expects), same as the frontend's `unknown` typing.
    """

    resume: Any
