"""FastAPI app factory (docs/13-spec-backend-api.md).

Run locally with: `uv run uvicorn finance_agent.api.app:create_app --factory --reload`
"""

from fastapi import FastAPI

from finance_agent.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Finance Agent API",
        description=(
            "Local-only FastAPI backend fronting the master LangGraph "
            "(docs/11-spec-orchestration-scheduling.md) — no cloud "
            "accounts, per CLAUDE.md."
        ),
    )
    app.include_router(router)
    return app
