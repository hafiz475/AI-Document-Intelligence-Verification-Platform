"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
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
    storage_path: str = "storage/documents"
    max_upload_bytes: int = 20 * 1024 * 1024
    ai_provider: Literal["disabled", "development", "openai"] = "disabled"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_provider: Literal["disabled", "development", "openai"] = "disabled"
    embedding_model: str = "deterministic-development-v1"
    embedding_dimensions: int = Field(default=64, ge=8, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=2048)
    openai_embedding_model: str = "text-embedding-3-small"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention configuration instance per process."""

    return Settings()
