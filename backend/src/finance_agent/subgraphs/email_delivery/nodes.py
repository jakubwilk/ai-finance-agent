"""Node factories for the email delivery subgraph
(docs/10-spec-email-delivery.md). Same DI pattern as every other subgraph
in this repo. Delivers the `REPORTS` `pending` queue only — `alert_immediate`
(docs/10 node 4) lives directly in `graph/master.py`, not here, since
docs/11's diagram draws it as a plain master-graph node, not a nested
subgraph.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Report
from finance_agent.subgraphs.email_delivery.smtp_client import SmtpClient
from finance_agent.subgraphs.email_delivery.state import (
    EmailDeliveryState,
    RenderedEmail,
    SendResult,
)

Node = Callable[[EmailDeliveryState], Awaitable[dict]]

# docs/10's own proposed default ("liczba prób do ustalenia, np. 3"),
# adopted as final — same treatment as BALANCE_TOLERANCE in
# subgraphs/verification/post_check_nodes.py: a technical/operational
# parameter, not a fact about the user, not worth a runtime config knob.
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5

_PLAIN_TEXT_FALLBACK = (
    "Ten e-mail zawiera raport finansowy w formacie HTML. Twój klient "
    "pocztowy nie wyświetla HTML — skontaktuj się z administratorem, aby "
    "zobaczyć pełną treść raportu."
)


def make_render_final_payload(session: AsyncSession) -> Node:
    async def _render_final_payload(_state: EmailDeliveryState) -> dict:
        pending_reports = (
            (
                await session.execute(
                    select(Report).where(Report.delivery_status == "pending")
                )
            )
            .scalars()
            .all()
        )

        pending: list[RenderedEmail] = [
            RenderedEmail(
                report_id=str(report.id),
                subject=(
                    f"Raport finansowy ({report.report_type}): "
                    f"{report.period_start.isoformat()} – "
                    f"{report.period_end.isoformat()}"
                ),
                html=report.content_html,
                plain_text=_PLAIN_TEXT_FALLBACK,
            )
            for report in pending_reports
        ]
        return {"pending": pending}

    return _render_final_payload


def make_send_smtp(
    smtp_client: SmtpClient,
    *,
    from_address: str,
    to_address: str,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Node:
    async def _send_smtp(state: EmailDeliveryState) -> dict:
        results: list[SendResult] = []
        for email in state["pending"]:
            message = EmailMessage()
            message["From"] = from_address
            message["To"] = to_address
            message["Subject"] = email["subject"]
            message.set_content(email["plain_text"])
            message.add_alternative(email["html"], subtype="html")

            last_error: str | None = None
            sent = False
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    await smtp_client.send(message)
                    sent = True
                    break
                except Exception as exc:  # noqa: BLE001 -- any SMTP failure means retry, then a failed SendResult, never a crashed graph
                    last_error = str(exc)
                    if attempt < RETRY_ATTEMPTS - 1:
                        await sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

            results.append(
                SendResult(
                    report_id=email["report_id"],
                    status="sent" if sent else "failed",
                    error=None if sent else last_error,
                )
            )

        return {"results": results}

    return _send_smtp


def make_handle_result(session: AsyncSession) -> Node:
    async def _handle_result(state: EmailDeliveryState) -> dict:
        for result in state["results"]:
            report = await session.get(Report, uuid.UUID(result["report_id"]))
            if result["status"] == "sent":
                report.delivery_status = "sent"
                report.sent_at = datetime.now(UTC)
            else:
                report.delivery_status = "failed"

        await session.flush()
        return {}

    return _handle_result
