"""Node factories for the verification post-check subgraph
(docs/03-spec-statement-verification.md, step 4). Pure DB arithmetic — no
Drive/PDF access, unlike pre-check/extraction.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Statement, Transaction
from finance_agent.subgraphs.verification.post_check_state import (
    PostCheckResult,
    PostCheckState,
)

Node = Callable[[PostCheckState], Awaitable[dict]]

# docs/03's proposed default, adopted as final — not worth a runtime config
# knob for a single rounding-tolerance constant.
BALANCE_TOLERANCE = Decimal("0.01")


def make_check_balance_consistency(session: AsyncSession) -> Node:
    async def _check_balance_consistency(_state: PostCheckState) -> dict:
        verified = (
            (
                await session.execute(
                    select(Statement).where(Statement.status == "verified")
                )
            )
            .scalars()
            .all()
        )

        results: list[PostCheckResult] = []
        for statement in verified:
            if statement.opening_balance is None or statement.closing_balance is None:
                results.append(
                    PostCheckResult(
                        statement_id=str(statement.id),
                        is_consistent=False,
                        failure_reason="no_transactions_extracted",
                    )
                )
                continue

            total = await session.scalar(
                select(func.sum(Transaction.amount)).where(
                    Transaction.statement_id == statement.id
                )
            )
            total = total if total is not None else Decimal(0)
            expected_closing = statement.opening_balance + total
            is_consistent = (
                abs(expected_closing - statement.closing_balance) <= BALANCE_TOLERANCE
            )

            results.append(
                PostCheckResult(
                    statement_id=str(statement.id),
                    is_consistent=is_consistent,
                    failure_reason=None if is_consistent else "balance_mismatch",
                )
            )

        return {"results": results}

    return _check_balance_consistency


def make_mark_result(session: AsyncSession) -> Node:
    async def _mark_result(state: PostCheckState) -> dict:
        for result in state["results"]:
            statement = await session.get(Statement, uuid.UUID(result["statement_id"]))
            if result["failure_reason"] is not None:
                statement.status = "failed"
                statement.failure_reason = result["failure_reason"]
            else:
                statement.status = "processed"

        await session.flush()

        all_ok = all(result["failure_reason"] is None for result in state["results"])
        return {"results": state["results"], "all_ok": all_ok}

    return _mark_result
