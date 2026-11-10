"""Embedding provider adapters.

The development provider is deterministic test infrastructure, not a production
semantic model.
"""

import hashlib
import math
import re
import time
from typing import TYPE_CHECKING, Any

from assureai_api.embedding_contracts import EmbeddingProvider, EmbeddingResult

if TYPE_CHECKING:
    from assureai_api.config import Settings


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingConfigurationError(EmbeddingProviderError):
    pass


_CANONICAL_TERMS = {
    "mechanical": "vibration",
    "vibrations": "vibration",
    "vibrational": "vibration",
    "issue": "abnormal",
    "issues": "abnormal",
    "problem": "abnormal",
    "problems": "abnormal",
    "damage": "defect",
    "damaged": "defect",
    "due": "date",
    "manufacturer": "manufacturer",
    "manufactured": "manufacturer",
    "maker": "manufacturer",
    "leaks": "leak",
    "leakage": "leak",
}


def _tokens(text: str) -> list[str]:
    values = re.findall(r"[a-z0-9]+", text.casefold())
    return [_CANONICAL_TERMS.get(value, value) for value in values if len(value) > 1]


def _normalized_hash_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokens(text)
    features = tokens + [f"{left}:{right}" for left, right in zip(tokens, tokens[1:], strict=False)]
    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        return [value / magnitude for value in vector]
    return vector


class DevelopmentEmbeddingProvider:
    """Deterministic, offline hashing provider for tests and demos."""

    provider_name = "development"
    model_name = "deterministic-development-v1"
    embedding_version = "development-hash-v1"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        started = time.perf_counter()
        vectors = [_normalized_hash_embedding(text, self.dimensions) for text in texts]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_name,
            model=self.model_name,
            dimensions=self.dimensions,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )

    def embed_query(self, query: str) -> EmbeddingResult:
        return self.embed_texts([query])


class OpenAIEmbeddingProvider:
    """OpenAI embeddings adapter returning only provider-neutral values."""

    provider_name = "openai"
    embedding_version = "openai-embeddings-v1"

    def __init__(self, *, api_key: str, model: str, dimensions: int) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("OpenAI embeddings require an API key.")
        from openai import OpenAI

        self.model_name = model
        self.dimensions = dimensions
        self._client: Any = OpenAI(api_key=api_key)

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                provider=self.provider_name,
                model=self.model_name,
                dimensions=self.dimensions,
                latency_ms=0,
            )
        started = time.perf_counter()
        try:
            response = self._client.embeddings.create(
                input=texts,
                model=self.model_name,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except Exception as exc:
            raise EmbeddingProviderError("OpenAI embedding request failed.") from exc
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts):
            raise EmbeddingProviderError("OpenAI returned an unexpected embedding count.")
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_name,
            model=self.model_name,
            dimensions=self.dimensions,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=response.usage.total_tokens if response.usage is not None else None,
        )

    def embed_query(self, query: str) -> EmbeddingResult:
        return self.embed_texts([query])


def create_embedding_provider(settings: "Settings") -> EmbeddingProvider:
    if settings.embedding_provider == "development":
        return DevelopmentEmbeddingProvider(settings.embedding_dimensions)
    if settings.embedding_provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return OpenAIEmbeddingProvider(
            api_key=key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    raise EmbeddingConfigurationError("Embedding generation is disabled.")


def embedding_identity(settings: "Settings") -> tuple[str, str, int, str]:
    if settings.embedding_provider == "development":
        return (
            DevelopmentEmbeddingProvider.provider_name,
            DevelopmentEmbeddingProvider.model_name,
            settings.embedding_dimensions,
            DevelopmentEmbeddingProvider.embedding_version,
        )
    if settings.embedding_provider == "openai":
        return (
            OpenAIEmbeddingProvider.provider_name,
            settings.openai_embedding_model,
            settings.embedding_dimensions,
            OpenAIEmbeddingProvider.embedding_version,
        )
    return "disabled", "disabled", settings.embedding_dimensions, "disabled"
