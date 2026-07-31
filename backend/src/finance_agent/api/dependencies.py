"""FastAPI dependencies for the backend API (docs/13-spec-backend-api.md).

`get_db_session`/`get_checkpointer`/`get_run_trigger` are the DI seam
PLAN.md step 12 flagged as missing — tests override them via
`app.dependency_overrides` to point at `TEST_DATABASE_URL` instead of the
dev `DATABASE_URL` every other real graph node uses, without touching the
dev database.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Header, HTTPException, status
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.config import settings
from finance_agent.db.session import async_session_factory
from finance_agent.graph.checkpointer import build_checkpointer
from finance_agent.graph.runner import run_master_graph


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with build_checkpointer() as checkpointer:
        yield checkpointer


def get_run_trigger() -> Callable[..., Awaitable[dict]]:
    """Returns the callable that actually executes/resumes the master
    graph. Default: the real `run_master_graph`. Tests override this to a
    fake that updates `RUNS` through the overridden `get_db_session`
    without touching the checkpointer/OVH/SMTP.
    """
    return run_master_graph


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Protects every route (docs/13 §Bezpieczeństwo — financial data,
    nothing exposed unauthenticated, not even `/health`). Identical 401 for
    "not configured" and "wrong key" — never reveal server configuration
    state to an unauthenticated caller.
    """
    if not settings.backend_api_key or x_api_key != settings.backend_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
