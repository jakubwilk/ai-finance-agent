import uuid
from datetime import date
from decimal import Decimal

from finance_agent.db.models import (
    Account,
    Category,
    FixedCost,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.cashflow.graph import build_cashflow_graph

EMPTY_STATE = {
    "statement_id": None,
    "transactions": [],
    "weekly": None,
    "fixed_costs_status": [],
    "rolling_month": None,
}


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_processed_statement(
    db_session,
    account: Account,
    *,
    period_start: date,
    period_end: date,
    drive_file_id: str = "file-1",
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="processed",
        period_start=period_start,
        period_end=period_end,
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("500.00"),
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


async def _make_category(db_session, name: str = "Rozrywka") -> Category:
    category = Category(name=name, score=50, type="expense")
    db_session.add(category)
    await db_session.flush()
    return category


async def _make_fixed_cost(
    db_session, category: Category, *, name: str, expected_amount: Decimal
) -> FixedCost:
    fixed_cost = FixedCost(
        category_id=category.id,
        name=name,
        expected_amount=expected_amount,
        frequency="monthly",
    )
    db_session.add(fixed_cost)
    await db_session.flush()
    return fixed_cost


async def _make_transaction(
    db_session,
    statement: Statement,
    *,
    amount: Decimal,
    category: Category | None = None,
    txn_date: date | None = None,
    review_status: str = "auto",
    matched_fixed_cost_id: uuid.UUID | None = None,
    description: str = "test",
) -> Transaction:
    transaction = Transaction(
        statement_id=statement.id,
        category_id=category.id if category else None,
        txn_date=txn_date if txn_date is not None else statement.period_end,
        amount=amount,
        description=description,
        review_status=review_status,
        matched_fixed_cost_id=matched_fixed_cost_id,
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction


async def test_aggregate_income_and_expense_totals(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_start=date(2026, 1, 8), period_end=date(2026, 1, 14)
    )
    category = await _make_category(db_session)
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("2000.00")
    )
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-300.00")
    )
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-50.00")
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["weekly"]["total_income"] == "2000.00"
    assert result["weekly"]["total_expense"] == "-350.00"


async def test_breakdown_by_category_includes_uncategorized(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_start=date(2026, 1, 8), period_end=date(2026, 1, 14)
    )
    category = await _make_category(db_session, name="Jedzenie")
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-100.00")
    )
    await _make_transaction(
        db_session, statement, category=None, amount=Decimal("-50.00")
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    breakdown = {
        e["category_name"]: e["total"] for e in result["weekly"]["category_breakdown"]
    }
    assert breakdown["Jedzenie"] == "-100.00"
    assert breakdown["Nieskategoryzowane"] == "-50.00"
    total = sum(Decimal(v) for v in breakdown.values())
    assert str(total) == result["weekly"]["total_expense"]


async def test_needs_review_included_and_counted(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_start=date(2026, 1, 8), period_end=date(2026, 1, 14)
    )
    category = await _make_category(db_session)
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("100.00")
    )
    await _make_transaction(
        db_session,
        statement,
        category=category,
        amount=Decimal("-20.00"),
        review_status="needs_review",
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["weekly"]["needs_review_count"] == 1
    assert result["weekly"]["total_expense"] == "-20.00"


async def test_fixed_costs_status_variants(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_start=date(2026, 1, 8), period_end=date(2026, 1, 14)
    )
    category = await _make_category(db_session, name="Subskrypcje")

    matched_cost = await _make_fixed_cost(
        db_session, category, name="Netflix", expected_amount=Decimal("43.00")
    )
    missing_cost = await _make_fixed_cost(
        db_session, category, name="Ubezpieczenie", expected_amount=Decimal("100.00")
    )
    changed_cost = await _make_fixed_cost(
        db_session, category, name="Prad", expected_amount=Decimal("50.00")
    )

    await _make_transaction(
        db_session,
        statement,
        category=category,
        amount=Decimal("-43.00"),
        matched_fixed_cost_id=matched_cost.id,
    )
    await _make_transaction(
        db_session,
        statement,
        category=category,
        amount=Decimal("-80.00"),
        matched_fixed_cost_id=changed_cost.id,
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    status_by_id = {s["fixed_cost_id"]: s for s in result["fixed_costs_status"]}
    assert status_by_id[str(matched_cost.id)]["status"] == "matched"
    assert status_by_id[str(missing_cost.id)]["status"] == "missing_payment"
    assert status_by_id[str(changed_cost.id)]["status"] == "amount_changed"


async def test_surplus_equals_income_plus_expense(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_start=date(2026, 1, 8), period_end=date(2026, 1, 14)
    )
    category = await _make_category(db_session)
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("500.00")
    )
    await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-200.00")
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["weekly"]["surplus"] == "300.00"


async def test_rolling_month_accumulates_across_statements(db_session):
    account = await _make_account(db_session)
    older_statement = await _make_processed_statement(
        db_session,
        account,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 7),
        drive_file_id="file-1",
    )
    latest_statement = await _make_processed_statement(
        db_session,
        account,
        period_start=date(2026, 1, 8),
        period_end=date(2026, 1, 14),
        drive_file_id="file-2",
    )
    category = await _make_category(db_session)
    await _make_transaction(
        db_session,
        older_statement,
        category=category,
        amount=Decimal("-100.00"),
        txn_date=date(2026, 1, 3),
    )
    await _make_transaction(
        db_session,
        latest_statement,
        category=category,
        amount=Decimal("-200.00"),
        txn_date=date(2026, 1, 10),
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    # weekly only reflects the current (latest) statement.
    assert result["weekly"]["total_expense"] == "-200.00"
    # rolling_month accumulates across both statements in the calendar month.
    assert result["rolling_month"]["total_expense"] == "-300.00"
    assert result["rolling_month"]["period_start"] == "2026-01-01"
    assert result["rolling_month"]["period_end"] == "2026-01-14"


async def test_no_processed_statement_is_noop(db_session):
    category = await _make_category(db_session)
    await _make_fixed_cost(
        db_session, category, name="Netflix", expected_amount=Decimal("43.00")
    )

    graph = build_cashflow_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == EMPTY_STATE
