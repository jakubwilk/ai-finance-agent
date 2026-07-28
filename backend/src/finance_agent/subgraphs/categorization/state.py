from typing_extensions import TypedDict


class CategorizationItem(TypedDict):
    """One `TRANSACTIONS` row being categorized (docs/06-spec-categorization.md).

    `amount` is kept as a string (not `Decimal`) because this state flows
    into `interrupt()`'s payload, which must be JSON-serializable.
    """

    transaction_id: str
    match_key: str
    counterparty: str | None
    description: str
    amount: str
    category_id: str | None
    category_name: str | None
    category_source: str | None
    category_confidence: float | None
    review_status: str


class CategorizationState(TypedDict):
    """State for the categorization subgraph. `items` has no reducer — same
    linear-pipeline style as every other subgraph in this repo.
    """

    items: list[CategorizationItem]
