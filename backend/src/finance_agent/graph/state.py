import operator
from typing import Annotated

from typing_extensions import TypedDict


class AlertDetail(TypedDict):
    """One failed `Statement`'s reason, for `_alert_immediate_node`
    (docs/10-spec-email-delivery.md) to build its message from — set by
    whichever verification node detects a failure, same "this run's
    outcome" role as `verification_ok` (not re-derived from the DB, since
    there's no "already alerted" tracking to avoid re-querying the same
    failed statement on a later run).
    """

    statement_id: str
    failure_reason: str | None


class MasterGraphState(TypedDict):
    """Shared state for the master orchestration graph.

    Deliberately minimal — just enough to drive the branching in
    docs/11-spec-orchestration-scheduling.md's flowchart. No `needs_review`
    field here (PLAN.md step 6/12): categorization's human review is
    entirely internal to that subgraph (`interrupt()` inside its own
    `human_review` node) — the master graph doesn't need to know or branch
    on it, unlike the original docs/11 sketch predating the real subgraph.
    """

    verification_ok: bool
    # Set (not accumulated — only one verification node fails per run) by
    # _verification_pre_check_node/_verification_post_check_node when
    # verification_ok is False.
    alert_details: list[AlertDetail]
    # Appended to by each placeholder node; lets tests assert which path
    # through the graph actually ran, not just that invoke() didn't raise.
    visited: Annotated[list[str], operator.add]
