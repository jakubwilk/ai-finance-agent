from datetime import date
from decimal import Decimal

from sqlalchemy import select

from finance_agent.db.models import (
    Account,
    Category,
    InvestmentRecommendation,
    Report,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.reporting.graph import build_reporting_graph

EMPTY_STATE = {
    "statement_id": None,
    "generate_monthly": False,
    "cashflow": None,
    "needs_review_items": [],
    "investment_recommendation": None,
    "monthly_comparison": None,
    "weekly_html": None,
    "monthly_html": None,
}


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_processed_statement(
    db_session, account: Account, *, period_end: date, drive_file_id: str
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="processed",
        period_start=date(period_end.year, period_end.month, 1),
        period_end=period_end,
        opening_balance=Decimal("0.00"),
        closing_balance=Decimal("1000.00"),
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


async def _make_category(db_session, name: str = "Jedzenie") -> Category:
    category = Category(name=name, score=50, type="expense")
    db_session.add(category)
    await db_session.flush()
    return category


async def _make_transaction(
    db_session,
    statement: Statement,
    *,
    amount: Decimal,
    category: Category | None = None,
    txn_date: date | None = None,
    review_status: str = "auto",
    description: str = "test",
) -> Transaction:
    transaction = Transaction(
        statement_id=statement.id,
        category_id=category.id if category else None,
        txn_date=txn_date if txn_date is not None else statement.period_end,
        amount=amount,
        description=description,
        review_status=review_status,
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction


async def _make_investment_recommendation(
    db_session,
    *,
    surplus_amount: Decimal = Decimal("100.00"),
    rationale: str = "test rationale",
    allocation_proposal: dict | None = None,
) -> InvestmentRecommendation:
    recommendation = InvestmentRecommendation(
        report_id=None,
        surplus_amount=surplus_amount,
        rationale=rationale,
        allocation_proposal=allocation_proposal or {"etf": "100.00"},
    )
    db_session.add(recommendation)
    await db_session.flush()
    return recommendation


async def test_weekly_report_contains_summary_and_breakdown(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    category = await _make_category(db_session, name="Jedzenie")
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("3200.00")
    )
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-1100.00")
    )

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert "3200.00 PLN" in result["weekly_html"]
    assert "-1100.00 PLN" in result["weekly_html"]
    assert "2100.00 PLN" in result["weekly_html"]  # surplus
    assert "Jedzenie" in result["weekly_html"]
    # 2026-01-14 is mid-month, not within the last 7 days -> no monthly report.
    assert result["generate_monthly"] is False
    assert result["monthly_html"] is None


async def test_no_recommendation_shows_default_no_surplus_message(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert "Brak nadwyżki do zainwestowania w tym okresie." in result["weekly_html"]


async def test_zero_surplus_recommendation_shows_its_own_rationale(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))
    await _make_investment_recommendation(
        db_session,
        surplus_amount=Decimal(0),
        rationale="Nadwyżka poniżej poduszki bezpieczeństwa",
    )

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert "Nadwyżka poniżej poduszki bezpieczeństwa" in result["weekly_html"]


async def test_needs_review_items_appear_in_weekly_report(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    category = await _make_category(db_session, name="Rozrywka")
    await _make_transaction(
        db_session,
        statement,
        category=category,
        amount=Decimal("-50.00"),
        review_status="needs_review",
        description="Nieznana transakcja",
    )

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert "Nieznana transakcja" in result["weekly_html"]
    assert "Rozrywka" in result["weekly_html"]
    assert "Transakcje do przeglądu" in result["weekly_html"]


async def test_no_needs_review_omits_section(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert "Transakcje do przeglądu" not in result["weekly_html"]


async def test_month_end_triggers_monthly_report_with_comparison(db_session):
    account = await _make_account(db_session)

    december_statement = await _make_processed_statement(
        db_session, account, period_end=date(2025, 12, 31), drive_file_id="file-dec"
    )
    await _make_transaction(
        db_session,
        december_statement,
        amount=Decimal("3000.00"),
        txn_date=date(2025, 12, 15),
    )
    await _make_transaction(
        db_session,
        december_statement,
        amount=Decimal("-1000.00"),
        txn_date=date(2025, 12, 20),
    )

    # 2026-01-28 is within the last 7 days of January -> month-end trigger.
    january_statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 28), drive_file_id="file-jan"
    )
    await _make_transaction(
        db_session,
        january_statement,
        amount=Decimal("3200.00"),
        txn_date=date(2026, 1, 28),
    )
    await _make_transaction(
        db_session,
        january_statement,
        amount=Decimal("-1100.00"),
        txn_date=date(2026, 1, 28),
    )

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["generate_monthly"] is True
    assert result["monthly_html"] is not None
    assert "3000.00 PLN" in result["monthly_html"]  # previous month income
    assert "-1000.00 PLN" in result["monthly_html"]  # previous month expense
    assert "2000.00 PLN" in result["monthly_html"]  # previous month surplus

    reports = (await db_session.execute(select(Report))).scalars().all()
    report_types = {r.report_type for r in reports}
    assert report_types == {"weekly", "monthly"}


async def test_mid_month_statement_does_not_trigger_monthly(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))

    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["generate_monthly"] is False
    assert result["monthly_html"] is None

    reports = (await db_session.execute(select(Report))).scalars().all()
    assert len(reports) == 1
    assert reports[0].report_type == "weekly"


async def test_persist_report_backfills_investment_recommendation(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 14), drive_file_id="file-1"
    )
    await _make_transaction(db_session, statement, amount=Decimal("500.00"))
    recommendation = await _make_investment_recommendation(db_session)

    graph = build_reporting_graph(session=db_session)
    await graph.ainvoke(EMPTY_STATE)

    weekly_report = (
        await db_session.execute(select(Report).where(Report.report_type == "weekly"))
    ).scalar_one()
    assert weekly_report.content_html

    await db_session.refresh(recommendation)
    assert recommendation.report_id == weekly_report.id


async def test_no_processed_statement_is_noop(db_session):
    graph = build_reporting_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["statement_id"] is None
    assert result["generate_monthly"] is False
    assert result["weekly_html"] is None
    assert result["monthly_html"] is None

    reports = (await db_session.execute(select(Report))).scalars().all()
    assert reports == []
