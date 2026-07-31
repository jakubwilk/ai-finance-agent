from collections.abc import Awaitable, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.email_delivery.nodes import (
    make_handle_result,
    make_render_final_payload,
    make_send_smtp,
)
from finance_agent.subgraphs.email_delivery.smtp_client import SmtpClient
from finance_agent.subgraphs.email_delivery.state import EmailDeliveryState

RENDER_FINAL_PAYLOAD = "render_final_payload"
SEND_SMTP = "send_smtp"
HANDLE_RESULT = "handle_result"


def build_email_delivery_graph(
    session: AsyncSession,
    smtp_client: SmtpClient,
    *,
    from_address: str,
    to_address: str,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> CompiledStateGraph:
    """Build the email delivery subgraph per docs/10-spec-email-delivery.md.
    Delivers the `REPORTS` `pending` queue — `alert_immediate` is a separate
    master-graph-level node, not part of this subgraph.
    """
    builder = StateGraph(EmailDeliveryState)

    builder.add_node(RENDER_FINAL_PAYLOAD, make_render_final_payload(session))
    send_smtp_kwargs = {"from_address": from_address, "to_address": to_address}
    if sleep is not None:
        send_smtp_kwargs["sleep"] = sleep
    builder.add_node(SEND_SMTP, make_send_smtp(smtp_client, **send_smtp_kwargs))
    builder.add_node(HANDLE_RESULT, make_handle_result(session))

    builder.add_edge(START, RENDER_FINAL_PAYLOAD)
    builder.add_edge(RENDER_FINAL_PAYLOAD, SEND_SMTP)
    builder.add_edge(SEND_SMTP, HANDLE_RESULT)
    builder.add_edge(HANDLE_RESULT, END)

    return builder.compile()
