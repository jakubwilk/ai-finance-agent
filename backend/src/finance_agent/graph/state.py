import operator
from typing import Annotated

from typing_extensions import TypedDict


class MasterGraphState(TypedDict):
    """Shared state for the master orchestration graph.

    Deliberately minimal for the skeleton stage: just enough to drive the
    branching in docs/11-spec-orchestration-scheduling.md's flowchart. Each
    subgraph will extend/populate this as it's implemented in later
    PLAN.md steps.
    """

    verification_ok: bool
    needs_review: bool
    # Appended to by each placeholder node; lets tests assert which path
    # through the graph actually ran, not just that invoke() didn't raise.
    visited: Annotated[list[str], operator.add]
