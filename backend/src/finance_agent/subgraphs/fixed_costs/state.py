from typing_extensions import TypedDict


class ReconciliationMatch(TypedDict):
    """One fixed cost's reconciliation outcome for the current statement
    period (docs/05-spec-fixed-costs.md). `status` is `None` until
    `flag_discrepancies` runs.
    """

    fixed_cost_id: str
    fixed_cost_name: str
    expected_amount: str
    transaction_id: str | None
    actual_amount: str | None
    status: str | None


class FixedCostsState(TypedDict):
    """State for the fixed costs reconciliation subgraph. `matches` has no
    reducer — same linear-pipeline style as every other subgraph in this
    repo, each node refining the same list.
    """

    statement_id: str | None
    matches: list[ReconciliationMatch]
