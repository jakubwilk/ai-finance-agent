from typing_extensions import TypedDict


class SafetyBufferResult(TypedDict):
    current_balance: str
    safety_buffer_amount: str
    investable_amount: str
    buffer_binding: bool


class TrendAssessment(TypedDict):
    """`historical_surplus` holds up to `TREND_LOOKBACK_PERIODS - 1`
    previous periods, most recent first (excludes the current period).
    """

    historical_surplus: list[str]
    is_anomaly: bool
    trend_note: str  # "insufficient_history" | "stable" | "anomaly_high_surplus"


class AllocationProposal(TypedDict):
    amount: str
    allocation: dict[str, str]
    rationale: str


class InvestmentState(TypedDict):
    """State for the investment analysis subgraph
    (docs/08-spec-investment-analysis.md).
    """

    statement_id: str | None
    surplus: str | None
    safety_buffer: SafetyBufferResult | None
    trend: TrendAssessment | None
    proposal: AllocationProposal | None
