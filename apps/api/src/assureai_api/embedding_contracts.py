"""Provider-neutral contracts for vector embeddings."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int = Field(ge=1)
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "EmbeddingResult":
        if any(len(vector) != self.dimensions for vector in self.vectors):
            raise ValueError("Every embedding must match the declared dimensions.")
        return self


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int
    embedding_version: str

    def embed_texts(self, texts: list[str]) -> EmbeddingResult: ...

    def embed_query(self, query: str) -> EmbeddingResult: ...
