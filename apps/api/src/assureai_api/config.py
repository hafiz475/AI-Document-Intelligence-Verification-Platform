"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets are supplied by the backend environment."""

    model_config = SettingsConfigDict(
        env_prefix="ASSUREAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AssureAI API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str | None = None
    redis_url: str | None = None
    ai_provider: Literal["disabled", "openai"] = "disabled"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention configuration instance per process."""

    return Settings()
