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
    auth_mode: Literal["disabled", "development", "oidc"] = "development"
    session_secret: SecretStr = SecretStr("development-only-change-me-32-bytes")
    session_cookie_name: str = "assureai_session"
    session_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    secure_cookies: bool = False
    database_url: str | None = None
    redis_url: str | None = None
    storage_provider: Literal["local", "azure_blob"] = "local"
    storage_path: str = "storage/documents"
    azure_storage_account_url: str | None = None
    azure_storage_container: str = "documents"
    secret_store_provider: Literal["environment", "azure_key_vault"] = "environment"
    key_vault_url: str | None = None
    malware_scanner: Literal["disabled", "clamav"] = "disabled"
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    max_upload_bytes: int = 20 * 1024 * 1024
    max_json_bytes: int = 1024 * 1024
    max_header_bytes: int = 32 * 1024
    rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    metrics_token: SecretStr | None = None
    https_enabled: bool = False
    otel_service_name: str = "assureai-api"
    otel_exporter_otlp_endpoint: str | None = None
    ai_provider: Literal["disabled", "development", "openai"] = "disabled"
    openai_api_key: SecretStr | None = None
    openai_api_key_ref: str | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_provider: Literal["disabled", "development", "openai"] = "disabled"
    embedding_model: str = "deterministic-development-v1"
    embedding_dimensions: int = Field(default=64, ge=8, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=2048)
    openai_embedding_model: str = "text-embedding-3-small"
    evaluation_max_cases: int = Field(default=200, ge=1, le=500)

    def validate_production_security(self) -> None:
        """Reject configurations that would silently disable production identity checks."""

        if self.environment == "production" and self.auth_mode == "disabled":
            raise ValueError("Production authentication cannot be disabled.")
        if (
            self.environment == "production"
            and self.auth_mode == "development"
            and self.session_secret.get_secret_value() == "development-only-change-me-32-bytes"
        ):
            raise ValueError("Production development auth requires a unique session secret.")
        if self.auth_mode == "oidc" and not all(
            (self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)
        ):
            raise ValueError("OIDC issuer, audience, and JWKS URL are required.")
        if self.storage_provider == "azure_blob" and not self.azure_storage_account_url:
            raise ValueError("Azure Blob Storage requires an account URL.")
        if self.secret_store_provider == "azure_key_vault" and not self.key_vault_url:
            raise ValueError("Azure Key Vault requires a vault URL.")


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention configuration instance per process."""

    return Settings()
