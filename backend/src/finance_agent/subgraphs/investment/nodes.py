"""Node factories for the investment analysis subgraph
(docs/08-spec-investment-analysis.md). Same DI pattern as every other
subgraph in this repo. Pure DB + LLM logic — no Drive/PDF access.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import (
    InvestmentRecommendation,
    InvestmentSettings,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.cashflow.nodes import (
    INCLUDED_REVIEW_STATUSES,
    compute_income_and_expense,
)
from finance_agent.subgraphs.investment.state import (
    AllocationProposal,
    InvestmentState,
    SafetyBufferResult,
    TrendAssessment,
)

Node = Callable[[InvestmentState], Awaitable[dict]]

# docs/08 only says "kilka ostatnich okresów" (a few recent periods) without
# a precise number — an implementation judgment call, not a personal fact to
# ask about. TREND_LOOKBACK_PERIODS includes the current period itself.
TREND_LOOKBACK_PERIODS = 4
ANOMALY_MULTIPLIER = Decimal(2)

# Confirmed with the user (PLAN.md step 9): risk profile "zbalansowany",
# instruments limited to these three (also the fixed AllocationResult
# schema below — function-calling is more robust with fixed fields than an
# arbitrary-keyed dict).
INSTRUMENT_KEYS = ("etf", "term_deposit", "savings_account")


class AllocationResult(BaseModel):
    etf_percent: float
    term_deposit_percent: float
    savings_account_percent: float
    rationale: str


async def _current_statement(session: AsyncSession) -> Statement | None:
    return (
        await session.execute(
            select(Statement)
            .where(Statement.status == "processed")
            .order_by(Statement.period_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _statement_surplus(session: AsyncSession, statement_id: uuid.UUID) -> Decimal:
    transactions = (
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.statement_id == statement_id,
                    Transaction.review_status.in_(INCLUDED_REVIEW_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    income, expense = compute_income_and_expense(transactions)
    return income + expense


def make_check_safety_buffer(session: AsyncSession) -> Node:
    async def _check_safety_buffer(_state: InvestmentState) -> dict:
        statement = await _current_statement(session)
        if statement is None:
            return {"statement_id": None, "surplus": None, "safety_buffer": None}

        settings_row = (
            (await session.execute(select(InvestmentSettings))).scalars().first()
        )
        if settings_row is None:
            return {
                "statement_id": str(statement.id),
                "surplus": None,
                "safety_buffer": None,
            }

        surplus = await _statement_surplus(session, statement.id)

        if surplus <= 0:
            investable_amount = Decimal(0)
        else:
            max_investable = max(
                statement.closing_balance - settings_row.safety_buffer_amount,
                Decimal(0),
            )
            investable_amount = min(surplus, max_investable)

        safety_buffer = SafetyBufferResult(
            current_balance=str(statement.closing_balance),
            safety_buffer_amount=str(settings_row.safety_buffer_amount),
            investable_amount=str(investable_amount),
            buffer_binding=investable_amount < surplus if surplus > 0 else False,
        )
        return {
            "statement_id": str(statement.id),
            "surplus": str(surplus),
            "safety_buffer": safety_buffer,
        }

    return _check_safety_buffer


def make_assess_trend(session: AsyncSession) -> Node:
    async def _assess_trend(state: InvestmentState) -> dict:
        if state["statement_id"] is None:
            return {"trend": None}

        statements = (
            (
                await session.execute(
                    select(Statement)
                    .where(Statement.status == "processed")
                    .order_by(Statement.period_end.desc())
                    .limit(TREND_LOOKBACK_PERIODS)
                )
            )
            .scalars()
            .all()
        )
        previous = statements[1:]  # statements[0] is the current period

        if not previous:
            return {
                "trend": TrendAssessment(
                    historical_surplus=[],
                    is_anomaly=False,
                    trend_note="insufficient_history",
                )
            }

        historical_surplus = [await _statement_surplus(session, s.id) for s in previous]
        average_previous = sum(historical_surplus) / len(historical_surplus)
        current_surplus = (
            Decimal(state["surplus"]) if state["surplus"] is not None else Decimal(0)
        )

        is_anomaly = (
            average_previous > 0
            and current_surplus > average_previous * ANOMALY_MULTIPLIER
        )
        trend_note = "anomaly_high_surplus" if is_anomaly else "stable"

        return {
            "trend": TrendAssessment(
                historical_surplus=[str(s) for s in historical_surplus],
                is_anomaly=is_anomaly,
                trend_note=trend_note,
            )
        }

    return _assess_trend


async def _propose_allocation(
    chat_model, risk_profile: str, instruments: list[str], amount: Decimal
) -> tuple[dict[str, float], str]:
    structured_model = chat_model.with_structured_output(
        AllocationResult, method="function_calling"
    )
    prompt = (
        f"Zaproponuj podział kwoty {amount} PLN nadwyżki finansowej między "
        f"dostępne instrumenty: {', '.join(instruments)}.\n"
        f"Profil ryzyka użytkownika: {risk_profile}.\n"
        "Procenty muszą sumować się do 100 i dotyczyć wyłącznie instrumentów "
        "z podanej listy (dla pozostałych ustaw 0%)."
    )
    try:
        result = await structured_model.ainvoke(prompt)
        percentages = {
            "etf": result.etf_percent,
            "term_deposit": result.term_deposit_percent,
            "savings_account": result.savings_account_percent,
        }
        allowed_percentages = {
            key: (pct if key in instruments else 0.0)
            for key, pct in percentages.items()
        }
        if abs(sum(allowed_percentages.values()) - 100) > 0.5:
            raise ValueError(
                "percentages do not sum to 100 within the allowed instruments"
            )
        return allowed_percentages, result.rationale
    except Exception:  # noqa: BLE001 -- any LLM/parsing failure means fall back to a safe deterministic split, not a crashed batch
        equal_share = 100 / len(instruments)
        return (
            {key: equal_share for key in instruments},
            (
                "LLM niedostępny lub zwrócił nieprawidłowy podział — zastosowano "
                "równy podział domyślny."
            ),
        )


def make_generate_allocation_proposal(chat_model, session: AsyncSession) -> Node:
    async def _generate_allocation_proposal(state: InvestmentState) -> dict:
        if state["safety_buffer"] is None:
            return {"proposal": None}

        investable_amount = Decimal(state["safety_buffer"]["investable_amount"])
        if investable_amount <= 0:
            reason = (
                "Nadwyżka poniżej poduszki bezpieczeństwa"
                if state["safety_buffer"]["buffer_binding"]
                else "Brak nadwyżki do zainwestowania"
            )
            return {
                "proposal": AllocationProposal(
                    amount="0",
                    allocation={key: "0" for key in INSTRUMENT_KEYS},
                    rationale=reason,
                )
            }

        proposal_amount = investable_amount
        trend = state["trend"]
        if trend is not None and trend["is_anomaly"] and trend["historical_surplus"]:
            average_previous = sum(
                Decimal(s) for s in trend["historical_surplus"]
            ) / len(trend["historical_surplus"])
            proposal_amount = min(investable_amount, average_previous)

        settings_row = (
            (await session.execute(select(InvestmentSettings))).scalars().first()
        )
        risk_profile = settings_row.risk_profile if settings_row else "balanced"
        instruments = (
            list(settings_row.instruments) if settings_row else list(INSTRUMENT_KEYS)
        )

        allocation_percentages, rationale = await _propose_allocation(
            chat_model, risk_profile, instruments, proposal_amount
        )

        allocation = {
            key: str(
                (proposal_amount * Decimal(str(pct)) / Decimal(100)).quantize(
                    Decimal("0.01")
                )
            )
            for key, pct in allocation_percentages.items()
        }

        return {
            "proposal": AllocationProposal(
                amount=str(proposal_amount),
                allocation=allocation,
                rationale=rationale,
            )
        }

    return _generate_allocation_proposal


def make_persist_recommendation(session: AsyncSession) -> Node:
    async def _persist_recommendation(state: InvestmentState) -> dict:
        proposal = state["proposal"]
        if proposal is None:
            return {}

        session.add(
            InvestmentRecommendation(
                report_id=None,
                surplus_amount=Decimal(proposal["amount"]),
                rationale=proposal["rationale"],
                allocation_proposal=proposal["allocation"],
            )
        )
        await session.flush()
        return {}

    return _persist_recommendation
