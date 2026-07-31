from typing_extensions import TypedDict


class NeedsReviewEntry(TypedDict):
    transaction_id: str
    description: str
    counterparty: str | None
    amount: str
    suggested_category: str | None


class MonthlyComparison(TypedDict):
    previous_month_income: str
    previous_month_expense: str
    previous_month_surplus: str


class InvestmentSummary(TypedDict):
    id: str
    surplus_amount: str
    rationale: str
    allocation_proposal: dict[str, str]


class ReportingState(TypedDict):
    """State for the reporting subgraph (docs/09-spec-reporting.md).

    `cashflow` holds the raw result of `build_cashflow_graph(...).ainvoke(...)`
    (docs/07) — `weekly`/`fixed_costs_status`/`rolling_month` keys, reused as
    a black box rather than re-derived field by field.
    """

    statement_id: str | None
    generate_monthly: bool
    cashflow: dict | None
    needs_review_items: list[NeedsReviewEntry]
    investment_recommendation: InvestmentSummary | None
    monthly_comparison: MonthlyComparison | None
    weekly_html: str | None
    monthly_html: str | None
