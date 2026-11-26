"""Provider-neutral secret lookup; secret values never cross the API boundary."""

import logging
import os
import re
from typing import Protocol

from pydantic import SecretStr

from assureai_api.config import Settings

_SAFE_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
logger = logging.getLogger(__name__)


class SecretStore(Protocol):
    provider: str

    def get(self, secret_ref: str) -> str: ...

    def close(self) -> None: ...


class EnvironmentSecretStore:
    provider = "environment"

    def get(self, secret_ref: str) -> str:
        if not _SAFE_ENV_NAME.fullmatch(secret_ref):
            raise ValueError("Invalid environment secret reference.")
        value = os.getenv(secret_ref)
        if value is None:
            raise KeyError("Configured secret is unavailable.")
        return value

    def close(self) -> None:
        return None


class AzureKeyVaultSecretStore:
    provider = "azure_key_vault"

    def __init__(self, vault_url: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        self._credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=self._credential)

    def get(self, secret_ref: str) -> str:
        value = self._client.get_secret(secret_ref).value
        if value is None:
            raise KeyError("Configured secret is unavailable.")
        return value

    def close(self) -> None:
        self._client.close()
        self._credential.close()


def create_secret_store(settings: Settings) -> SecretStore:
    if settings.secret_store_provider == "azure_key_vault":
        assert settings.key_vault_url is not None
        return AzureKeyVaultSecretStore(settings.key_vault_url)
    return EnvironmentSecretStore()


def resolve_provider_secrets(settings: Settings, store: SecretStore) -> None:
    """Resolve configured references into process memory without exposing them over HTTP."""

    if settings.openai_api_key is None and settings.openai_api_key_ref:
        settings.openai_api_key = SecretStr(store.get(settings.openai_api_key_ref))
        logger.info(
            "secret.used", extra={"secret_provider": store.provider, "secret_purpose": "ai"}
        )
