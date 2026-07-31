from typing_extensions import TypedDict


class TransactionRecord(TypedDict):
    """Working set for the current statement, populated by
    `aggregate_income_expense`, consumed by `breakdown_by_category`
    (docs/07-spec-cashflow-calculation.md).
    """

    transaction_id: str
    category_id: str | None
    amount: str
    review_status: str


class CategoryBreakdownEntry(TypedDict):
    category_id: str | None
    category_name: str
    total: str


class FixedCostStatusEntry(TypedDict):
    """Reconciliation status read from `Transaction.matched_fixed_cost_id`
    (already persisted by the fixed_costs_reconciliation subgraph, docs/05)
    — this subgraph reads that result, it does not redo the matching.
    """

    fixed_cost_id: str
    fixed_cost_name: str
    expected_amount: str
    actual_amount: str | None
    status: str


class PeriodSummary(TypedDict):
    period_start: str
    period_end: str
    total_income: str
    total_expense: str
    category_breakdown: list[CategoryBreakdownEntry]
    needs_review_count: int
    surplus: str


class CashflowState(TypedDict):
    """State for the cashflow calculation subgraph. `weekly` covers the
    current statement's own period; `rolling_month` covers the calendar
    month to date across every statement in it.
    """

    statement_id: str | None
    transactions: list[TransactionRecord]
    weekly: PeriodSummary | None
    fixed_costs_status: list[FixedCostStatusEntry]
    rolling_month: PeriodSummary | None
