"""Provider-neutral contracts for evidence-backed answer generation."""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from assureai_api.models import RagSupportStatus


class RagCitationReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    page_number: int | None
    quote: str = Field(min_length=1)


class RagAnswerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    support_status: RagSupportStatus
    citations: list[RagCitationReference]

    @model_validator(mode="after")
    def validate_answer_text(self) -> "RagAnswerOutput":
        if not self.answer.strip():
            raise ValueError("answer must not be blank")
        return self


class RagProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structured_data: dict[str, Any]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class RagContextChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int | None
    similarity_score: float
    content: str


class RagAnswerProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult: ...
