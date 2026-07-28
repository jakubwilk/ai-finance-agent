import asyncio
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from finance_agent.config import settings
from finance_agent.db.models import Account, Statement, Transaction

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


async def _can_connect(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect():
            return True
    except Exception:  # noqa: BLE001 -- any connection failure means "skip", regardless of driver-specific type
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _migrated_test_db():
    """Upgrades TEST_DATABASE_URL to head before this module's tests, downgrades
    to base after — proves migrations work both directions on a clean DB
    (docs/01-spec-data-model.md's acceptance criteria).

    Skips (rather than fails) if TEST_DATABASE_URL isn't configured/reachable,
    e.g. when Docker Compose's postgres service isn't running.
    """
    url = settings.test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping DB integration tests")
    if not asyncio.run(_can_connect(url)):
        pytest.skip(
            f"Cannot connect to TEST_DATABASE_URL ({url}); is `docker compose up` running?"
        )

    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest.fixture
async def session():
    engine = create_async_engine(settings.test_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session
    await engine.dispose()


async def test_migration_creates_all_tables(session):
    result = await session.execute(
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


async def test_transaction_requires_existing_statement(session):
    session.add(
        Transaction(
            statement_id=uuid.uuid4(),
            txn_date=date(2026, 1, 1),
            amount=Decimal("10.00"),
            description="orphan transaction",
            review_status="auto",
        )
    )

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_statement_unique_account_and_drive_file(session):
    account = Account(
        account_type="private", display_name="Test Account", bank_name="Test Bank"
    )
    session.add(account)
    await session.commit()

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

    session.add(make_statement())
    await session.commit()

    session.add(make_statement())
    with pytest.raises(IntegrityError):
        await session.commit()
