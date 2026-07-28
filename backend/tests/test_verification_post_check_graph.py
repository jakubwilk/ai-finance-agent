from datetime import date
from decimal import Decimal

from finance_agent.db.models import Account, Statement, Transaction
from finance_agent.subgraphs.verification.post_check_graph import (
    build_post_check_graph,
)

EMPTY_STATE = {"results": [], "all_ok": True}


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_verified_statement(
    db_session,
    account: Account,
    *,
    opening_balance: Decimal | None,
    closing_balance: Decimal | None,
    drive_file_id: str = "file-1",
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="verified",
        opening_balance=opening_balance,
        closing_balance=closing_balance,
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


async def test_consistent_balances_mark_processed(db_session):
    account = await _make_account(db_session)
    statement = await _make_verified_statement(
        db_session,
        account,
        opening_balance=Decimal("100.00"),
        closing_balance=Decimal("80.00"),
    )
    db_session.add(
        Transaction(
            statement_id=statement.id,
            txn_date=date(2026, 1, 1),
            amount=Decimal("-20.00"),
            description="test",
            review_status="auto",
        )
    )
    await db_session.flush()

    graph = build_post_check_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is True
    await db_session.refresh(statement)
    assert statement.status == "processed"
    assert statement.failure_reason is None


async def test_off_by_exactly_tolerance_still_passes(db_session):
    account = await _make_account(db_session)
    statement = await _make_verified_statement(
        db_session,
        account,
        opening_balance=Decimal("100.00"),
        closing_balance=Decimal("79.99"),
    )
    db_session.add(
        Transaction(
            statement_id=statement.id,
            txn_date=date(2026, 1, 1),
            amount=Decimal("-20.00"),
            description="test",
            review_status="auto",
        )
    )
    await db_session.flush()

    graph = build_post_check_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is True
    await db_session.refresh(statement)
    assert statement.status == "processed"


async def test_mismatch_beyond_tolerance_is_marked_failed(db_session):
    account = await _make_account(db_session)
    statement = await _make_verified_statement(
        db_session,
        account,
        opening_balance=Decimal("100.00"),
        closing_balance=Decimal("50.00"),
    )
    db_session.add(
        Transaction(
            statement_id=statement.id,
            txn_date=date(2026, 1, 1),
            amount=Decimal("-20.00"),
            description="test",
            review_status="auto",
        )
    )
    await db_session.flush()

    graph = build_post_check_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "balance_mismatch"


async def test_no_transactions_extracted_is_marked_failed(db_session):
    account = await _make_account(db_session)
    statement = await _make_verified_statement(
        db_session, account, opening_balance=None, closing_balance=None
    )

    graph = build_post_check_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "no_transactions_extracted"


async def test_zero_verified_statements_completes_with_all_ok_true(db_session):
    graph = build_post_check_graph(session=db_session)
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == {"results": [], "all_ok": True}
