"""Tests `_upsert_cashflow_summary` (`graph/master.py`) directly — same
style as `tests/test_alert_immediate.py`'s direct import of
`_build_alert_message` despite the leading underscore. This is the piece
that used to not exist at all: `_cashflow_calculation_node` computed the
full `cashflow_calculation` subgraph result and threw it away instead of
persisting it, so `GET /runs/{thread_id}/cashflow` had nothing to read.
"""

from sqlalchemy import select

from finance_agent.db.models import CashflowSummary, Run
from finance_agent.graph.master import _upsert_cashflow_summary

_RESULT = {
    "statement_id": "11111111-1111-1111-1111-111111111111",
    "transactions": [],
    "weekly": {
        "period_start": "2026-01-01",
        "period_end": "2026-01-07",
        "total_income": "1000.00",
        "total_expense": "-400.00",
        "category_breakdown": [
            {
                "category_id": None,
                "category_name": "Nieskategoryzowane",
                "total": "-400.00",
            }
        ],
        "needs_review_count": 0,
        "surplus": "600.00",
    },
    "rolling_month": None,
    "fixed_costs_status": [],
}


async def test_upsert_cashflow_summary_creates_then_updates(db_session):
    db_session.add(Run(thread_id="thread-cf", status="running"))
    await db_session.flush()

    created = await _upsert_cashflow_summary("thread-cf", _RESULT, session=db_session)
    assert created.thread_id == "thread-cf"
    assert created.statement_id == _RESULT["statement_id"]
    assert created.weekly == _RESULT["weekly"]
    assert created.rolling_month is None
    assert created.fixed_costs_status == []

    updated_result = dict(_RESULT, statement_id="22222222-2222-2222-2222-222222222222")
    updated = await _upsert_cashflow_summary(
        "thread-cf", updated_result, session=db_session
    )
    assert updated.statement_id == "22222222-2222-2222-2222-222222222222"

    all_summaries = (await db_session.execute(select(CashflowSummary))).scalars().all()
    assert len(all_summaries) == 1
