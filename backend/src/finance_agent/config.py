from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / `.env`.

    All fields are optional for now: most of their real values are still
    open questions (see PLAN.md "Otwarte kwestie") and later PLAN.md steps
    will start consuming them one at a time. Nothing here should hard-fail
    at import time just because `.env` isn't fully filled in yet.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None
    test_database_url: str | None = None

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_refresh_token: str | None = None
    google_drive_folder_id: str | None = None

    ollama_base_url: str | None = None
    ollama_model_classification: str | None = None
    ollama_model_investment: str | None = None
    ollama_model_reporting: str | None = None
    ollama_api_key: str | None = None

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None

    report_recipient_email: str | None = None


settings = Settings()
