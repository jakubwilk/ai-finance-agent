from datetime import date

from finance_agent.db.models import Report
from finance_agent.subgraphs.email_delivery.graph import build_email_delivery_graph

EMPTY_STATE = {"pending": [], "results": []}

FROM_ADDRESS = "agent@example.com"
TO_ADDRESS = "user@example.com"


class FakeSmtpClient:
    """`outcomes` is consumed one per `send()` call — `None` succeeds,
    an `Exception` instance raises it. Lets a test script exactly the
    retry-then-succeed / always-fail sequences it wants to prove.
    """

    def __init__(self, outcomes: list[Exception | None]):
        self._outcomes = list(outcomes)
        self.sent_messages = []
        self.call_count = 0

    async def send(self, message):
        self.call_count += 1
        outcome = self._outcomes.pop(0)
        if outcome is not None:
            raise outcome
        self.sent_messages.append(message)


async def _no_op_sleep(_seconds: float) -> None:
    return None


async def _make_report(
    db_session,
    *,
    delivery_status: str = "pending",
    report_type: str = "weekly",
    period_start: date = date(2026, 1, 8),
    period_end: date = date(2026, 1, 14),
    content_html: str = "<html><body>test report</body></html>",
) -> Report:
    report = Report(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        content_html=content_html,
        delivery_status=delivery_status,
    )
    db_session.add(report)
    await db_session.flush()
    return report


async def test_successful_send_marks_report_sent(db_session):
    report = await _make_report(db_session)
    smtp_client = FakeSmtpClient(outcomes=[None])

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["results"] == [
        {"report_id": str(report.id), "status": "sent", "error": None}
    ]
    await db_session.refresh(report)
    assert report.delivery_status == "sent"
    assert report.sent_at is not None
    assert len(smtp_client.sent_messages) == 1


async def test_persistent_failure_marks_report_failed_without_raising(db_session):
    report = await _make_report(db_session)
    smtp_client = FakeSmtpClient(
        outcomes=[
            RuntimeError("smtp down"),
            RuntimeError("smtp down"),
            RuntimeError("smtp down"),
        ]
    )

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["error"] == "smtp down"
    assert smtp_client.call_count == 3

    await db_session.refresh(report)
    assert report.delivery_status == "failed"
    assert report.sent_at is None


async def test_retry_then_success_marks_sent(db_session):
    report = await _make_report(db_session)
    smtp_client = FakeSmtpClient(outcomes=[RuntimeError("transient"), None])

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["results"][0]["status"] == "sent"
    assert smtp_client.call_count == 2

    await db_session.refresh(report)
    assert report.delivery_status == "sent"


async def test_only_pending_reports_are_collected(db_session):
    await _make_report(db_session, delivery_status="sent")
    pending_report = await _make_report(db_session, delivery_status="pending")
    smtp_client = FakeSmtpClient(outcomes=[None])

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert len(result["results"]) == 1
    assert result["results"][0]["report_id"] == str(pending_report.id)


async def test_no_pending_reports_is_noop(db_session):
    smtp_client = FakeSmtpClient(outcomes=[])

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == {"pending": [], "results": []}
    assert smtp_client.call_count == 0


async def test_email_subject_contains_report_type_and_period(db_session):
    await _make_report(
        db_session,
        report_type="monthly",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    smtp_client = FakeSmtpClient(outcomes=[None])

    graph = build_email_delivery_graph(
        session=db_session,
        smtp_client=smtp_client,
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
        sleep=_no_op_sleep,
    )
    await graph.ainvoke(EMPTY_STATE)

    sent_message = smtp_client.sent_messages[0]
    assert "monthly" in sent_message["Subject"]
    assert "2026-01-01" in sent_message["Subject"]
    assert "2026-01-31" in sent_message["Subject"]
    assert sent_message["From"] == FROM_ADDRESS
    assert sent_message["To"] == TO_ADDRESS
