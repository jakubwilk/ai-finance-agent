"""Node factories for the reporting subgraph (docs/09-spec-reporting.md).
Same DI pattern as every other subgraph in this repo. No LLM involved —
`build_reporting_model()` (`llm/client.py`, step 5) stays unused for now;
nothing in docs/09's node list calls for LLM reasoning, only template
filling.
"""

import calendar
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta

from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import (
    Category,
    InvestmentRecommendation,
    Report,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.cashflow.graph import build_cashflow_graph
from finance_agent.subgraphs.cashflow.nodes import (
    INCLUDED_REVIEW_STATUSES,
    compute_income_and_expense,
)
from finance_agent.subgraphs.reporting.state import (
    InvestmentSummary,
    MonthlyComparison,
    NeedsReviewEntry,
    ReportingState,
)

Node = Callable[[ReportingState], Awaitable[dict]]

# docs/11 says the monthly report fires "on the first run after the end of
# the calendar month" without pinning down the exact test — an
# implementation judgment call given weekly cadence, not a fabricated fact.
MONTH_END_WINDOW_DAYS = 7

_JINJA_ENV = Environment(
    loader=PackageLoader("finance_agent.subgraphs.reporting", "templates"),
    autoescape=select_autoescape(),
)

_EMPTY_CASHFLOW_STATE = {
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


def make_determine_report_types(session: AsyncSession) -> Node:
    async def _determine_report_types(_state: ReportingState) -> dict:
        statement = await _current_statement(session)
        if statement is None:
            return {"statement_id": None, "generate_monthly": False}

        days_in_month = calendar.monthrange(
            statement.period_end.year, statement.period_end.month
        )[1]
        generate_monthly = (
            days_in_month - statement.period_end.day
        ) < MONTH_END_WINDOW_DAYS

        return {
            "statement_id": str(statement.id),
            "generate_monthly": generate_monthly,
        }

    return _determine_report_types


def make_render_weekly(session: AsyncSession) -> Node:
    async def _render_weekly(state: ReportingState) -> dict:
        if state["statement_id"] is None:
            return {"weekly_html": None}

        cashflow = await build_cashflow_graph(session=session).ainvoke(
            _EMPTY_CASHFLOW_STATE
        )

        needs_review_transactions = (
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.statement_id == uuid.UUID(state["statement_id"]),
                        Transaction.review_status == "needs_review",
                    )
                )
            )
            .scalars()
            .all()
        )
        category_ids = {
            t.category_id for t in needs_review_transactions if t.category_id
        }
        category_name_by_id = (
            {
                c.id: c.name
                for c in (
                    await session.execute(
                        select(Category).where(Category.id.in_(category_ids))
                    )
                ).scalars()
            }
            if category_ids
            else {}
        )
        needs_review_items: list[NeedsReviewEntry] = [
            NeedsReviewEntry(
                transaction_id=str(t.id),
                description=t.description,
                counterparty=t.counterparty,
                amount=str(t.amount),
                suggested_category=category_name_by_id.get(t.category_id),
            )
            for t in needs_review_transactions
        ]

        recommendation_row = (
            await session.execute(
                select(InvestmentRecommendation)
                .where(InvestmentRecommendation.report_id.is_(None))
                .order_by(InvestmentRecommendation.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        investment_recommendation = (
            InvestmentSummary(
                id=str(recommendation_row.id),
                surplus_amount=str(recommendation_row.surplus_amount),
                rationale=recommendation_row.rationale,
                allocation_proposal=recommendation_row.allocation_proposal,
            )
            if recommendation_row is not None
            else None
        )

        template = _JINJA_ENV.get_template("weekly.html.jinja")
        weekly_html = template.render(
            weekly=cashflow["weekly"],
            fixed_costs_status=cashflow["fixed_costs_status"],
            needs_review_items=needs_review_items,
            investment_recommendation=investment_recommendation,
        )

        return {
            "cashflow": cashflow,
            "needs_review_items": needs_review_items,
            "investment_recommendation": investment_recommendation,
            "weekly_html": weekly_html,
        }

    return _render_weekly


def make_render_monthly(session: AsyncSession) -> Node:
    async def _render_monthly(state: ReportingState) -> dict:
        if not state["generate_monthly"] or state["cashflow"] is None:
            return {"monthly_html": None}

        rolling_month = state["cashflow"]["rolling_month"]
        current_month_start = date.fromisoformat(rolling_month["period_start"])

        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)

        transactions = (
            (
                await session.execute(
                    select(Transaction)
                    .join(Statement, Transaction.statement_id == Statement.id)
                    .where(
                        Statement.status == "processed",
                        Transaction.txn_date >= previous_month_start,
                        Transaction.txn_date <= previous_month_end,
                        Transaction.review_status.in_(INCLUDED_REVIEW_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )
        previous_income, previous_expense = compute_income_and_expense(transactions)
        monthly_comparison = MonthlyComparison(
            previous_month_income=str(previous_income),
            previous_month_expense=str(previous_expense),
            previous_month_surplus=str(previous_income + previous_expense),
        )

        template = _JINJA_ENV.get_template("monthly.html.jinja")
        monthly_html = template.render(
            rolling_month=rolling_month,
            monthly_comparison=monthly_comparison,
            investment_recommendation=state["investment_recommendation"],
        )

        return {
            "monthly_comparison": monthly_comparison,
            "monthly_html": monthly_html,
        }

    return _render_monthly


def make_persist_report(session: AsyncSession) -> Node:
    async def _persist_report(state: ReportingState) -> dict:
        if state["weekly_html"] is None:
            return {}

        weekly_summary = state["cashflow"]["weekly"]
        weekly_report = Report(
            report_type="weekly",
            period_start=date.fromisoformat(weekly_summary["period_start"]),
            period_end=date.fromisoformat(weekly_summary["period_end"]),
            content_html=state["weekly_html"],
            delivery_status="pending",
        )
        session.add(weekly_report)
        await session.flush()

        if state["generate_monthly"] and state["monthly_html"] is not None:
            rolling_month = state["cashflow"]["rolling_month"]
            session.add(
                Report(
                    report_type="monthly",
                    period_start=date.fromisoformat(rolling_month["period_start"]),
                    period_end=date.fromisoformat(rolling_month["period_end"]),
                    content_html=state["monthly_html"],
                    delivery_status="pending",
                )
            )

        if state["investment_recommendation"] is not None:
            recommendation = await session.get(
                InvestmentRecommendation,
                uuid.UUID(state["investment_recommendation"]["id"]),
            )
            recommendation.report_id = weekly_report.id

        await session.flush()
        return {}

    return _persist_report
