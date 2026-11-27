"""Read models for the product workspace without duplicating domain state."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from assureai_api.models import DocumentStatus, ReviewStatus
from assureai_api.schemas import DocumentResponse, ExtractedFieldResponse, ExtractionRunResponse


class UsageSummary(BaseModel):
    extraction_tokens: int | None
    rag_tokens: int | None
    evaluation_tokens: int | None
    total_tokens: int | None
    average_provider_latency_ms: float | None
    records_with_token_usage: int


class ProviderUsage(BaseModel):
    provider: str
    model: str
    operation: str
    requests: int


class OverviewMetrics(BaseModel):
    documents: int
    documents_ready: int
    documents_failed: int
    extraction_runs: int
    fields_awaiting_review: int
    verified_fields: int
    rag_questions: int
    supported_answers: int
    insufficient_evidence_answers: int
    evaluation_pass_rate: float | None
    average_retrieval_latency_ms: float | None
    average_rag_latency_ms: float | None


class ActivityItem(BaseModel):
    id: str
    event_type: str
    target_type: str | None
    target_id: str | None
    document_id: str | None
    actor: str | None
    created_at: datetime


class ProjectOverviewResponse(BaseModel):
    metrics: OverviewMetrics
    usage: UsageSummary
    provider_usage: list[ProviderUsage]
    recent_activity: list[ActivityItem]


class DocumentIndexResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class ReviewQueueItem(BaseModel):
    document_id: str
    document_name: str
    extraction_run_id: str
    provider: str
    model: str
    field: ExtractedFieldResponse


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int


class AuditItem(BaseModel):
    id: str
    event_type: str
    actor: str | None
    document_id: str | None
    target_type: str | None
    target_id: str | None
    request_id: str | None
    trace_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


class AuditIndexResponse(BaseModel):
    items: list[AuditItem]
    total: int
    limit: int
    offset: int


class DocumentReportResponse(BaseModel):
    document: DocumentResponse
    latest_extraction: ExtractionRunResponse | None
    question_count: int
    supported_answer_count: int
    insufficient_answer_count: int


class DocumentIndexFilters(BaseModel):
    status: DocumentStatus | None = None
    mime_type: str | None = Field(default=None, max_length=100)


class ReviewQueueFilters(BaseModel):
    status: ReviewStatus | None = None
    document_id: str | None = None
    field_name: str | None = Field(default=None, max_length=100)
