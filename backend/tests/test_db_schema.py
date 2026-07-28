import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from finance_agent.db.models import Account, Statement, Transaction


async def test_migration_creates_all_tables(db_session):
    result = await db_session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    tables = {row[0] for row in result}

    assert {
        "accounts",
        "statements",
        "transactions",
        "categories",
        "fixed_costs",
        "reports",
        "investment_recommendations",
    } <= tables


async def test_transaction_requires_existing_statement(db_session):
    db_session.add(
        Transaction(
            statement_id=uuid.uuid4(),
            txn_date=date(2026, 1, 1),
            amount=Decimal("10.00"),
            description="orphan transaction",
            review_status="auto",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_statement_unique_account_and_drive_file(db_session):
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.commit()

    def make_statement() -> Statement:
        return Statement(
            account_id=account.id,
            drive_file_id="same-file-id",
            file_name="statement.pdf",
            checksum="abc123",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("0.00"),
            status="pending",
        )

    db_session.add(make_statement())
    await db_session.commit()

    db_session.add(make_statement())
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_statement_period_and_balance_columns_are_nullable(db_session):
    """Ingestion's persist_metadata inserts a Statement before verification
    has parsed the PDF header/footer — period/balance columns must accept
    NULL until verification pre-check fills them in (docs/02, docs/03)."""
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()

    db_session.add(
        Statement(
            account_id=account.id,
            drive_file_id="file-id",
            file_name="statement.pdf",
            checksum="abc123",
            status="pending",
        )
    )
    await db_session.commit()
