"""Node factories for the fixed costs reconciliation subgraph
(docs/05-spec-fixed-costs.md). Same DI pattern as every other subgraph in
this repo. Pure DB logic — no Drive/PDF access, runs after categorization so
every fixed cost's expected category is already populated on the matching
transaction.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import FixedCost, Statement, Transaction
from finance_agent.subgraphs.fixed_costs.state import (
    FixedCostsState,
    ReconciliationMatch,
)

Node = Callable[[FixedCostsState], Awaitable[dict]]

# docs/05's proposed example tolerance (5%), confirmed with the user as the
# final value — not a runtime config knob, same treatment as
# BALANCE_TOLERANCE/DEFAULT_THRESHOLD in the other subgraphs. Gates the
# *discrepancy classification* (matched vs. amount_changed), not whether a
# match exists at all — see make_flag_discrepancies.
AMOUNT_TOLERANCE_RATIO = Decimal("0.05")


def make_load_fixed_costs(session: AsyncSession) -> Node:
    async def _load_fixed_costs(_state: FixedCostsState) -> dict:
        statement = (
            await session.execute(
                select(Statement)
                .where(Statement.status == "processed")
                .order_by(Statement.period_end.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        fixed_costs = (await session.execute(select(FixedCost))).scalars().all()

        if statement is None or not fixed_costs:
            return {"statement_id": None, "matches": []}

        matches: list[ReconciliationMatch] = [
            ReconciliationMatch(
                fixed_cost_id=str(fc.id),
                fixed_cost_name=fc.name,
                expected_amount=str(fc.expected_amount),
                transaction_id=None,
                actual_amount=None,
                status=None,
            )
            for fc in fixed_costs
        ]
        return {"statement_id": str(statement.id), "matches": matches}

    return _load_fixed_costs


def make_match_transactions(session: AsyncSession) -> Node:
    async def _match_transactions(state: FixedCostsState) -> dict:
        if state["statement_id"] is None or not state["matches"]:
            return {"matches": state["matches"]}

        fixed_cost_ids = [uuid.UUID(m["fixed_cost_id"]) for m in state["matches"]]
        fixed_costs = (
            (
                await session.execute(
                    select(FixedCost).where(FixedCost.id.in_(fixed_cost_ids))
                )
            )
            .scalars()
            .all()
        )
        category_id_by_fixed_cost_id = {fc.id: fc.category_id for fc in fixed_costs}

        transactions = (
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.statement_id == uuid.UUID(state["statement_id"]),
                        Transaction.matched_fixed_cost_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        claimed: set[uuid.UUID] = set()
        updated: list[ReconciliationMatch] = []
        for match in state["matches"]:
            fixed_cost_id = uuid.UUID(match["fixed_cost_id"])
            category_id = category_id_by_fixed_cost_id.get(fixed_cost_id)
            expected_amount = Decimal(match["expected_amount"])

            candidates = [
                t
                for t in transactions
                if t.category_id == category_id and t.id not in claimed
            ]
            if not candidates:
                updated.append(match)
                continue

            best = min(candidates, key=lambda t: abs(abs(t.amount) - expected_amount))
            claimed.add(best.id)
            updated.append(
                {
                    **match,
                    "transaction_id": str(best.id),
                    "actual_amount": str(best.amount),
                }
            )

        return {"matches": updated}

    return _match_transactions


def make_flag_discrepancies() -> Node:
    async def _flag_discrepancies(state: FixedCostsState) -> dict:
        updated: list[ReconciliationMatch] = []
        for match in state["matches"]:
            if match["transaction_id"] is None:
                status = "missing_payment"
            else:
                expected_amount = Decimal(match["expected_amount"])
                actual_amount = Decimal(match["actual_amount"])
                tolerance = expected_amount * AMOUNT_TOLERANCE_RATIO
                status = (
                    "matched"
                    if abs(abs(actual_amount) - expected_amount) <= tolerance
                    else "amount_changed"
                )
            updated.append({**match, "status": status})

        return {"matches": updated}

    return _flag_discrepancies


def make_persist_reconciliation(session: AsyncSession) -> Node:
    async def _persist_reconciliation(state: FixedCostsState) -> dict:
        for match in state["matches"]:
            if match["transaction_id"] is None:
                continue
            transaction = await session.get(
                Transaction, uuid.UUID(match["transaction_id"])
            )
            transaction.matched_fixed_cost_id = uuid.UUID(match["fixed_cost_id"])

        await session.flush()
        return {"matches": state["matches"]}

    return _persist_reconciliation
