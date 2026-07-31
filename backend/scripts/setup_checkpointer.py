"""Create the LangGraph checkpointer's tables (`checkpoints`, `checkpoint_writes`
etc.) in Postgres — docs/11-spec-orchestration-scheduling.md.

Usage: uv run python scripts/setup_checkpointer.py

Run this once per environment (local dev, each deployment target) —
**never at application startup** (LangGraph's own guidance: `.setup()` is a
one-time schema operation, not something to repeat on every process boot).
These tables are managed entirely by `langgraph-checkpoint-postgres`, not
by the Alembic migrations in `alembic/versions/` — a deliberately separate
schema-management path (docs/01's "Uwagi projektowe" note on the
checkpointer).

On Windows, `psycopg`'s async mode is incompatible with the default
`ProactorEventLoop` — verified directly (`psycopg.InterfaceError: Psycopg
cannot use the 'ProactorEventLoop' to run in async mode`) — so this switches
to `WindowsSelectorEventLoopPolicy` before starting the loop. `asyncpg`
(used elsewhere via SQLAlchemy) works fine under either policy, so this is
safe process-wide.
"""

import asyncio
import sys

from finance_agent.graph.checkpointer import build_checkpointer

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main() -> None:
    async with build_checkpointer() as checkpointer:
        await checkpointer.setup()
    print("Checkpointer tables created (or already present).")


if __name__ == "__main__":
    asyncio.run(main())
