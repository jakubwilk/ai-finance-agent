"""Node factories for the cashflow calculation subgraph
(docs/07-spec-cashflow-calculation.md). Same DI pattern as every other
subgraph in this repo. Pure DB logic — no Drive/PDF access, runs after
fixed_costs_reconciliation so `Transaction.matched_fixed_cost_id` is already
populated where applicable.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Category, FixedCost, Statement, Transaction
from finance_agent.subgraphs.cashflow.state import (
    CashflowState,
    CategoryBreakdownEntry,
    FixedCostStatusEntry,
    PeriodSummary,
    TransactionRecord,
)
from finance_agent.subgraphs.fixed_costs.nodes import AMOUNT_TOLERANCE_RATIO

Node = Callable[[CashflowState], Awaitable[dict]]

# docs/07: transactions still pending human confirmation are included in the
# totals (using the LLM's tentative category) rather than excluded — the
# money already left the account regardless of review status. Surfaced via
# `needs_review_count` so the report (docs/09, not yet built) can warn about
# it instead of silently presenting unconfirmed categorization as certain.
INCLUDED_REVIEW_STATUSES = ("auto", "confirmed", "needs_review")

_NO_OP_RESULT = {
    "statement_id": None,
    "transactions": [],
    "weekly": None,
    "fixed_costs_status": [],
    "rolling_month": None,
}


async def _current_statement(session: AsyncSession) -> Statement | None:
    return (
        await session.execute(
            select(Statement)
            .where(Statement.status == "processed")
            .order_by(Statement.period_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _category_name_by_id(session: AsyncSession) -> dict[uuid.UUID, str]:
    categories = (await session.execute(select(Category))).scalars().all()
    return {c.id: c.name for c in categories}


def compute_income_and_expense(
    transactions: list[Transaction],
) -> tuple[Decimal, Decimal]:
    """Shared by `aggregate_income_expense`/`compute_rolling_month` here and
    by `subgraphs/investment/nodes.py` (current + historical periods for
    trend assessment) — same cross-subgraph reuse as
    `fixed_costs.nodes.AMOUNT_TOLERANCE_RATIO`.
    """
    total_income = Decimal(0)
    total_expense = Decimal(0)
    for t in transactions:
        if t.amount > 0:
            total_income += t.amount
        else:
            total_expense += t.amount
    return total_income, total_expense


def make_aggregate_income_expense(session: AsyncSession) -> Node:
    async def _aggregate_income_expense(_state: CashflowState) -> dict:
        statement = await _current_statement(session)
        if statement is None:
            return dict(_NO_OP_RESULT)

        transactions = (
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.statement_id == statement.id,
                        Transaction.review_status.in_(INCLUDED_REVIEW_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )

        total_income, total_expense = compute_income_and_expense(transactions)
        needs_review_count = sum(
            1 for t in transactions if t.review_status == "needs_review"
        )
        records: list[TransactionRecord] = [
            TransactionRecord(
                transaction_id=str(t.id),
                category_id=str(t.category_id) if t.category_id else None,
                amount=str(t.amount),
                review_status=t.review_status,
            )
            for t in transactions
        ]

        weekly = PeriodSummary(
            period_start=statement.period_start.isoformat(),
            period_end=statement.period_end.isoformat(),
            total_income=str(total_income),
            total_expense=str(total_expense),
            category_breakdown=[],
            needs_review_count=needs_review_count,
            surplus="0",
        )
        return {
            "statement_id": str(statement.id),
            "transactions": records,
            "weekly": weekly,
        }

    return _aggregate_income_expense


def make_breakdown_by_category(session: AsyncSession) -> Node:
    async def _breakdown_by_category(state: CashflowState) -> dict:
        if state["weekly"] is None:
            return {}

        category_name_by_id = await _category_name_by_id(session)

        totals_by_category: dict[str | None, Decimal] = {}
        for record in state["transactions"]:
            key = record["category_id"]
            totals_by_category[key] = totals_by_category.get(key, Decimal(0)) + Decimal(
                record["amount"]
            )

        category_breakdown = [
            CategoryBreakdownEntry(
                category_id=category_id,
                category_name=category_name_by_id.get(
                    uuid.UUID(category_id), "Nieskategoryzowane"
                )
                if category_id
                else "Nieskategoryzowane",
                total=str(total),
            )
            for category_id, total in totals_by_category.items()
        ]

        return {"weekly": {**state["weekly"], "category_breakdown": category_breakdown}}

    return _breakdown_by_category


def make_apply_fixed_costs_status(session: AsyncSession) -> Node:
    async def _apply_fixed_costs_status(state: CashflowState) -> dict:
        if state["statement_id"] is None:
            return {"fixed_costs_status": []}

        fixed_costs = (await session.execute(select(FixedCost))).scalars().all()
        if not fixed_costs:
            return {"fixed_costs_status": []}

        matched_transactions = (
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.statement_id == uuid.UUID(state["statement_id"]),
                        Transaction.matched_fixed_cost_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        matched_by_fixed_cost_id = {
            t.matched_fixed_cost_id: t for t in matched_transactions
        }

        statuses: list[FixedCostStatusEntry] = []
        for fc in fixed_costs:
            matched_txn = matched_by_fixed_cost_id.get(fc.id)
            if matched_txn is None:
                statuses.append(
                    FixedCostStatusEntry(
                        fixed_cost_id=str(fc.id),
                        fixed_cost_name=fc.name,
                        expected_amount=str(fc.expected_amount),
                        actual_amount=None,
                        status="missing_payment",
                    )
                )
                continue

            tolerance = fc.expected_amount * AMOUNT_TOLERANCE_RATIO
            within_tolerance = (
                abs(abs(matched_txn.amount) - fc.expected_amount) <= tolerance
            )
            statuses.append(
                FixedCostStatusEntry(
                    fixed_cost_id=str(fc.id),
                    fixed_cost_name=fc.name,
                    expected_amount=str(fc.expected_amount),
                    actual_amount=str(matched_txn.amount),
                    status="matched" if within_tolerance else "amount_changed",
                )
            )

        return {"fixed_costs_status": statuses}

    return _apply_fixed_costs_status


def make_compute_surplus() -> Node:
    async def _compute_surplus(state: CashflowState) -> dict:
        if state["weekly"] is None:
            return {}

        total_income = Decimal(state["weekly"]["total_income"])
        total_expense = Decimal(state["weekly"]["total_expense"])
        return {
            "weekly": {**state["weekly"], "surplus": str(total_income + total_expense)}
        }

    return _compute_surplus


def make_compute_rolling_month(session: AsyncSession) -> Node:
    async def _compute_rolling_month(state: CashflowState) -> dict:
        if state["statement_id"] is None:
            return {"rolling_month": None}

        statement = await session.get(Statement, uuid.UUID(state["statement_id"]))
        month_start = statement.period_end.replace(day=1)

        transactions = (
            (
                await session.execute(
                    select(Transaction)
                    .join(Statement, Transaction.statement_id == Statement.id)
                    .where(
                        Statement.status == "processed",
                        Transaction.txn_date >= month_start,
                        Transaction.txn_date <= statement.period_end,
                        Transaction.review_status.in_(INCLUDED_REVIEW_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )

        category_name_by_id = await _category_name_by_id(session)

        total_income, total_expense = compute_income_and_expense(transactions)
        needs_review_count = sum(
            1 for t in transactions if t.review_status == "needs_review"
        )
        totals_by_category: dict[uuid.UUID | None, Decimal] = {}
        for t in transactions:
            totals_by_category[t.category_id] = (
                totals_by_category.get(t.category_id, Decimal(0)) + t.amount
            )

        category_breakdown = [
            CategoryBreakdownEntry(
                category_id=str(category_id) if category_id else None,
                category_name=category_name_by_id.get(category_id, "Nieskategoryzowane")
                if category_id
                else "Nieskategoryzowane",
                total=str(total),
            )
            for category_id, total in totals_by_category.items()
        ]

        rolling_month = PeriodSummary(
            period_start=month_start.isoformat(),
            period_end=statement.period_end.isoformat(),
            total_income=str(total_income),
            total_expense=str(total_expense),
            category_breakdown=category_breakdown,
            needs_review_count=needs_review_count,
            surplus=str(total_income + total_expense),
        )
        return {"rolling_month": rolling_month}

    return _compute_rolling_month
