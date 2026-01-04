"""
Application configuration using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://assistant:assistant@localhost:5432/assistant"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Telegram
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_webhook_secret: str = ""

    # Web App
    webapp_url: str = "https://corben.pro"
    domain: str = "corben.pro"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"  # For parsing
    openai_whisper_model: str = "whisper-1"  # For speech-to-text

    # Encryption
    encryption_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Microsoft OAuth
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    # Notion OAuth
    notion_client_id: str = ""
    notion_client_secret: str = ""

    # JWT for session management
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # API Settings
    api_prefix: str = "/api"
    debug: bool = False

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.webapp_url}/integrations/google"

    @property
    def microsoft_redirect_uri(self) -> str:
        return f"{self.webapp_url}/integrations/microsoft"

    @property
    def notion_redirect_uri(self) -> str:
        return f"{self.webapp_url}/integrations/notion"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
