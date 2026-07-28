"""LLM client foundation (docs/12-spec-llm-integration-ollama.md).

OVH AI Endpoints is a serverless, OpenAI-API-compatible service (confirmed
against its live catalog and current LangChain docs, not from memory) — so
this goes through `langchain_openai.ChatOpenAI` with a custom `base_url`,
not `langchain-ollama`. `timeout`/`max_retries` satisfy docs/12's
"timeout i retry z backoff" requirement natively.

This module only builds clients — task-specific logic (classification
prompts, investment reasoning, report generation) and task-specific
fallback behavior belong to the steps that consume these (docs/06, 08, 09).
"""

from langchain_openai import ChatOpenAI

from finance_agent.config import Settings
from finance_agent.config import settings as default_settings

TIMEOUT_SECONDS = 60
MAX_RETRIES = 3


def build_chat_model(
    model: str | None,
    *,
    model_var_name: str = "<model>",
    settings: Settings = default_settings,
) -> ChatOpenAI:
    missing = [
        var_name
        for var_name, value in (
            ("OVH_AI_ENDPOINTS_BASE_URL", settings.ovh_ai_endpoints_base_url),
            ("OVH_AI_ENDPOINTS_API_KEY", settings.ovh_ai_endpoints_api_key),
            (model_var_name, model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing OVH AI Endpoints config: {', '.join(missing)}. "
            "Set them in backend/.env — see docs/12-spec-llm-integration-ollama.md."
        )

    return ChatOpenAI(
        model=model,
        base_url=settings.ovh_ai_endpoints_base_url,
        api_key=settings.ovh_ai_endpoints_api_key,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def build_classification_model(*, settings: Settings = default_settings) -> ChatOpenAI:
    return build_chat_model(
        settings.ovh_model_classification,
        model_var_name="OVH_MODEL_CLASSIFICATION",
        settings=settings,
    )


def build_investment_model(*, settings: Settings = default_settings) -> ChatOpenAI:
    return build_chat_model(
        settings.ovh_model_investment,
        model_var_name="OVH_MODEL_INVESTMENT",
        settings=settings,
    )


def build_reporting_model(*, settings: Settings = default_settings) -> ChatOpenAI:
    return build_chat_model(
        settings.ovh_model_reporting,
        model_var_name="OVH_MODEL_REPORTING",
        settings=settings,
    )
