import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from finance_agent.config import settings

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


@pytest.fixture(scope="session", autouse=True)
def migrated_test_db():
    """Upgrades TEST_DATABASE_URL to head before the test session, downgrades
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
async def db_session():
    engine = create_async_engine(settings.test_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
