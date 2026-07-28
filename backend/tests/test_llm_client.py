import pytest

from finance_agent.config import Settings
from finance_agent.llm.client import (
    MAX_RETRIES,
    TIMEOUT_SECONDS,
    build_chat_model,
    build_classification_model,
    build_investment_model,
    build_reporting_model,
)

FULL_SETTINGS = Settings(
    ovh_ai_endpoints_base_url="https://example.com/v1",
    ovh_ai_endpoints_api_key="secret-key",
    ovh_model_classification="gpt-oss-20b",
    ovh_model_investment="gpt-oss-120b",
    ovh_model_reporting="Mistral-Small-3.2-24B-Instruct-2506",
)


def test_build_chat_model_raises_clear_error_when_base_url_and_key_missing():
    settings = Settings(
        ovh_ai_endpoints_base_url=None,
        ovh_ai_endpoints_api_key=None,
    )

    with pytest.raises(
        RuntimeError, match="OVH_AI_ENDPOINTS_BASE_URL.*OVH_AI_ENDPOINTS_API_KEY"
    ):
        build_chat_model("some-model", settings=settings)


def test_build_chat_model_raises_clear_error_naming_missing_model_var():
    settings = Settings(
        ovh_ai_endpoints_base_url="https://example.com/v1",
        ovh_ai_endpoints_api_key="secret-key",
    )

    with pytest.raises(RuntimeError, match="OVH_MODEL_CLASSIFICATION"):
        build_chat_model(
            None, model_var_name="OVH_MODEL_CLASSIFICATION", settings=settings
        )


def test_build_chat_model_constructs_expected_client():
    model = build_chat_model("gpt-oss-20b", settings=FULL_SETTINGS)

    assert model.model_name == "gpt-oss-20b"
    assert model.openai_api_base == "https://example.com/v1"
    assert model.openai_api_key.get_secret_value() == "secret-key"
    assert model.request_timeout == TIMEOUT_SECONDS
    assert model.max_retries == MAX_RETRIES


def test_build_classification_model_uses_classification_setting():
    model = build_classification_model(settings=FULL_SETTINGS)
    assert model.model_name == "gpt-oss-20b"


def test_build_investment_model_uses_investment_setting():
    model = build_investment_model(settings=FULL_SETTINGS)
    assert model.model_name == "gpt-oss-120b"


def test_build_reporting_model_uses_reporting_setting():
    model = build_reporting_model(settings=FULL_SETTINGS)
    assert model.model_name == "Mistral-Small-3.2-24B-Instruct-2506"
