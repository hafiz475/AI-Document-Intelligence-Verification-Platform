"""Typed HTTP request and response contracts."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from assureai_api.models import (
    DocumentStatus,
    EmbeddingRunStatus,
    ExtractionRunStatus,
    ReviewStatus,
    SupportStatus,
)


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]
    service: str
    version: str


class ProjectCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = (
        Field(examples=["Wind Farm Alpha"])
    )
    description: str | None = Field(default=None, max_length=4000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    filename: str = Field(validation_alias="original_filename")
    mime_type: str
    file_size: int
    sha256_hash: str
    status: DocumentStatus
    page_count: int | None
    character_count: int | None
    processing_error: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    page_number: int | None
    section: str | None
    content: str
    character_count: int
    metadata: dict[str, Any] = Field(validation_alias="chunk_metadata")
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    limit: int
    offset: int


class PromptVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    schema_version: str
    created_at: datetime


class ExtractionEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_chunk_id: str
    page_number: int | None
    quote: str
    created_at: datetime


class ExtractedFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    extraction_run_id: str
    document_id: str
    field_name: str
    field_type: str
    raw_value: Any | None
    normalized_value: Any | None
    missing_reason: str | None
    corrected_value: Any | None
    review_status: ReviewStatus
    support_status: SupportStatus
    review_reason: str | None
    reviewer: str | None
    reviewed_at: datetime | None
    evidence: list[ExtractionEvidenceResponse]
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    extracted_field_id: str | None
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    reviewer: str | None
    created_at: datetime


class ExtractionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    document_id: str
    status: ExtractionRunStatus
    provider: str
    model: str
    prompt_version: PromptVersionResponse
    started_at: datetime | None
    completed_at: datetime | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    error_message: str | None
    fields: list[ExtractedFieldResponse]
    audit_events: list[AuditEventResponse]
    created_at: datetime
    updated_at: datetime


class FieldReviewRequest(BaseModel):
    decision: ReviewStatus
    value: str | list[str] | None = None
    reason: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ] = None

    @model_validator(mode="after")
    def validate_decision(self) -> "FieldReviewRequest":
        if self.decision == ReviewStatus.UNREVIEWED:
            raise ValueError("UNREVIEWED is not a review decision")
        if self.decision == ReviewStatus.CORRECTED and self.value is None:
            raise ValueError("CORRECTED requires a value")
        if self.decision in {ReviewStatus.CORRECTED, ReviewStatus.REJECTED} and not self.reason:
            raise ValueError(f"{self.decision.value} requires a reason")
        if self.decision != ReviewStatus.CORRECTED and self.value is not None:
            raise ValueError("value is accepted only for CORRECTED")
        return self


class EmbeddingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    document_id: str
    status: EmbeddingRunStatus
    provider: str
    model: str
    dimensions: int
    embedding_version: str
    chunks_total: int
    chunks_embedded: int
    latency_ms: int | None
    input_tokens: int | None
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SemanticSearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)


class SemanticSearchResultResponse(BaseModel):
    rank: int
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity_score: float
    metadata: dict[str, object]
    embedding_model: str


class SemanticSearchResponse(BaseModel):
    query: str
    provider: str
    model: str
    dimensions: int
    metric: Literal["cosine_similarity"] = "cosine_similarity"
    query_embedding_latency_ms: int
    search_latency_ms: int
    results: list[SemanticSearchResultResponse]


class RetrievalEvaluationCaseRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    expected_chunk_ids: list[str] = Field(min_length=1)
    document_id: str | None = None


class RetrievalEvaluationRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    cases: list[RetrievalEvaluationCaseRequest] = Field(min_length=1, max_length=100)


class RetrievalEvaluationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query: str
    expected_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    first_relevant_rank: int | None
    hit: bool
    recall: float
    reciprocal_rank: float


class RetrievalEvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    embedding_provider: str
    embedding_model: str
    top_k: int
    case_count: int
    hit_rate: float
    mean_reciprocal_rank: float
    recall_at_k: float
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    case_results: list[RetrievalEvaluationCaseResponse]
