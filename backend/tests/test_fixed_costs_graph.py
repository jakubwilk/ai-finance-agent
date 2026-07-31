from datetime import date
from decimal import Decimal

from finance_agent.db.models import (
    Account,
    Category,
    FixedCost,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.fixed_costs.graph import build_fixed_costs_graph

EMPTY_STATE = {"statement_id": None, "matches": []}


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_processed_statement(
    db_session, account: Account, *, period_end: date, drive_file_id: str = "file-1"
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="processed",
        period_start=date(period_end.year, period_end.month, 1),
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
    category: Category | None,
    amount: Decimal,
    description: str = "test",
) -> Transaction:
    transaction = Transaction(
        statement_id=statement.id,
        category_id=category.id if category else None,
        txn_date=statement.period_end,
        amount=amount,
        description=description,
        review_status="auto",
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction


async def test_matched_transaction_within_tolerance(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 31)
    )
    category = await _make_category(db_session)
    fixed_cost = await _make_fixed_cost(
        db_session, category, name="Netflix", expected_amount=Decimal("43.00")
    )
    transaction = await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-43.00")
    )

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["fixed_cost_id"] == str(fixed_cost.id)
    assert match["transaction_id"] == str(transaction.id)
    assert match["status"] == "matched"

    await db_session.refresh(transaction)
    assert transaction.matched_fixed_cost_id == fixed_cost.id


async def test_missing_payment_when_no_candidate_in_category(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 31)
    )
    category = await _make_category(db_session)
    other_category = await _make_category(db_session, name="Jedzenie")
    fixed_cost = await _make_fixed_cost(
        db_session, category, name="Netflix", expected_amount=Decimal("43.00")
    )
    # Only a transaction in a different category exists this period.
    await _make_transaction(
        db_session, statement, category=other_category, amount=Decimal("-43.00")
    )

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["fixed_cost_id"] == str(fixed_cost.id)
    assert match["transaction_id"] is None
    assert match["status"] == "missing_payment"


async def test_amount_changed_when_matched_beyond_tolerance(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 31)
    )
    category = await _make_category(db_session)
    fixed_cost = await _make_fixed_cost(
        db_session, category, name="Ubezpieczenie", expected_amount=Decimal("100.00")
    )
    # 20% off expected_amount, well beyond the 5% tolerance.
    transaction = await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-80.00")
    )

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["transaction_id"] == str(transaction.id)
    assert match["status"] == "amount_changed"

    # Still linked — it IS the corresponding payment, just a different amount.
    await db_session.refresh(transaction)
    assert transaction.matched_fixed_cost_id == fixed_cost.id


async def test_empty_fixed_costs_table_is_noop(db_session):
    account = await _make_account(db_session)
    await _make_processed_statement(db_session, account, period_end=date(2026, 1, 31))

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == {"statement_id": None, "matches": []}


async def test_no_processed_statement_is_noop(db_session):
    category = await _make_category(db_session)
    await _make_fixed_cost(
        db_session, category, name="Netflix", expected_amount=Decimal("43.00")
    )

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == {"statement_id": None, "matches": []}


async def test_two_fixed_costs_same_category_claim_different_transactions(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session, account, period_end=date(2026, 1, 31)
    )
    category = await _make_category(db_session)
    cheap_cost = await _make_fixed_cost(
        db_session, category, name="Spotify", expected_amount=Decimal("50.00")
    )
    expensive_cost = await _make_fixed_cost(
        db_session, category, name="Czynsz", expected_amount=Decimal("100.00")
    )
    cheap_txn = await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-50.00")
    )
    expensive_txn = await _make_transaction(
        db_session, statement, category=category, amount=Decimal("-100.00")
    )

    graph = build_fixed_costs_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    matches_by_fixed_cost_id = {m["fixed_cost_id"]: m for m in result["matches"]}
    assert matches_by_fixed_cost_id[str(cheap_cost.id)]["transaction_id"] == str(
        cheap_txn.id
    )
    assert matches_by_fixed_cost_id[str(expensive_cost.id)]["transaction_id"] == str(
        expensive_txn.id
    )
    assert matches_by_fixed_cost_id[str(cheap_cost.id)]["status"] == "matched"
    assert matches_by_fixed_cost_id[str(expensive_cost.id)]["status"] == "matched"
