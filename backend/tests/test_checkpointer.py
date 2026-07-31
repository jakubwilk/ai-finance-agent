import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from finance_agent.config import Settings, settings
from finance_agent.graph.checkpointer import (
    build_checkpointer,
    psycopg_dsn_from_database_url,
)


def test_psycopg_dsn_from_database_url_strips_asyncpg_dialect():
    assert (
        psycopg_dsn_from_database_url("postgresql+asyncpg://user:pass@host:5432/db")
        == "postgresql://user:pass@host:5432/db"
    )


def test_psycopg_dsn_from_database_url_leaves_plain_dsn_unchanged():
    assert (
        psycopg_dsn_from_database_url("postgresql://user:pass@host:5432/db")
        == "postgresql://user:pass@host:5432/db"
    )


def test_build_checkpointer_raises_clear_error_when_database_url_missing():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        build_checkpointer(settings=Settings(database_url=None))


async def _can_connect(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect():
            return True
    except Exception:  # noqa: BLE001 -- any connection failure means "skip"
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _skip_if_test_db_unreachable():
    """Same skip-not-fail convention as `migrated_test_db` in conftest.py —
    this test needs a real, reachable Postgres to prove `.setup()` actually
    creates tables (that's the whole point, not something to fake).
    """
    url = settings.test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping checkpointer integration test")
    if not asyncio.run(_can_connect(url)):
        pytest.skip(
            f"Cannot connect to TEST_DATABASE_URL ({url}); is `docker compose up` running?"
        )


async def test_setup_creates_checkpointer_tables():
    test_settings = Settings(database_url=settings.test_database_url)

    async with build_checkpointer(settings=test_settings) as checkpointer:
        await checkpointer.setup()

    engine = create_async_engine(settings.test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename LIKE 'checkpoint%'"
                )
            )
            tables = {row[0] for row in result}
    finally:
        await engine.dispose()

    assert {"checkpoints", "checkpoint_writes", "checkpoint_blobs"} <= tables
