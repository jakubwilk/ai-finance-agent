from typing_extensions import TypedDict


class RenderedEmail(TypedDict):
    report_id: str
    subject: str
    html: str
    plain_text: str


class SendResult(TypedDict):
    report_id: str
    status: str  # "sent" | "failed"
    error: str | None


class EmailDeliveryState(TypedDict):
    """State for the email delivery subgraph (docs/10-spec-email-delivery.md).

    Covers the `REPORTS` pending queue only — `alert_immediate` is a
    separate, non-subgraph node in `graph/master.py` (docs/11's diagram
    draws it as a plain master-graph node, not a nested subgraph).
    """

    pending: list[RenderedEmail]
    results: list[SendResult]
