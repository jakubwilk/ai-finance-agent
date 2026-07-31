"""Postgres-backed checkpointer for the master graph
(docs/11-spec-orchestration-scheduling.md).

`langgraph-checkpoint-postgres` uses `psycopg` (v3), not the `asyncpg`
driver SQLAlchemy already uses in this project — same Postgres instance,
a second, checkpointer-only driver. Needs `psycopg[binary]` specifically
(not bare `psycopg`): the pure-Python/C extension variant requires a
system `libpq` install, which isn't guaranteed on every dev machine —
verified directly (bare `psycopg` failed to import here with "no pq
wrapper available" until the `binary` extra was added).
"""

from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from finance_agent.config import Settings
from finance_agent.config import settings as default_settings


def psycopg_dsn_from_database_url(database_url: str) -> str:
    """SQLAlchemy's `DATABASE_URL` is `postgresql+asyncpg://...`; psycopg
    doesn't understand the `+asyncpg` dialect suffix and expects a plain
    `postgresql://...` DSN — same host/user/password/db, different driver.
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def build_checkpointer(
    *, settings: Settings = default_settings
) -> AbstractAsyncContextManager[AsyncPostgresSaver]:
    """Returns the `async with` context manager itself (not yet entered) —
    `AsyncPostgresSaver.from_conn_string(...)` is `@asynccontextmanager`,
    so the caller controls its lifetime with `async with build_checkpointer() as checkpointer:`.

    Tables must exist already (`scripts/setup_checkpointer.py`, run once —
    never at application startup, per LangGraph's own guidance).
    """
    if not settings.database_url:
        raise RuntimeError(
            "Missing DATABASE_URL. Set it in backend/.env — see "
            "docs/11-spec-orchestration-scheduling.md."
        )

    return AsyncPostgresSaver.from_conn_string(
        psycopg_dsn_from_database_url(settings.database_url)
    )
