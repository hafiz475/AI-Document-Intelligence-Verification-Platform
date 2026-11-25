"""HTTP contracts for unified evaluation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from assureai_api.models import (
    EvaluationCaseResultStatus,
    EvaluationRunStatus,
    EvaluationType,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EvaluationDatasetCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    evaluation_type: EvaluationType


class EvaluationCaseUpsert(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationCaseResponse(ApiModel):
    id: str
    dataset_id: str
    name: str
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EvaluationDatasetResponse(ApiModel):
    id: str
    project_id: str
    name: str
    description: str | None
    evaluation_type: EvaluationType
    case_count: int
    cases: list[EvaluationCaseResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EvaluationRunCreate(ApiModel):
    dataset_id: str
    prompt_version_id: str | None = None
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    embedding_provider: str | None = Field(default=None, max_length=100)
    embedding_model: str | None = Field(default=None, max_length=200)
    top_k: int = Field(default=5, ge=1, le=20)


class EvaluationCaseResultResponse(ApiModel):
    id: str
    evaluation_run_id: str
    evaluation_case_id: str
    status: EvaluationCaseResultStatus
    score: float | None
    metrics_json: dict[str, Any]
    case_snapshot_json: dict[str, Any]
    actual_output_json: dict[str, Any]
    error_message: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    created_at: datetime


class EvaluationRunResponse(ApiModel):
    id: str
    project_id: str
    dataset_id: str
    evaluation_type: EvaluationType
    status: EvaluationRunStatus
    prompt_version_id: str | None
    provider: str
    model: str
    embedding_provider: str | None
    embedding_model: str | None
    evaluator_version: str
    configuration_json: dict[str, Any]
    aggregate_metrics_json: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    total_cases: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    average_score: float | None
    average_latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    error_message: str | None
    case_results: list[EvaluationCaseResultResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RegressionThresholds(ApiModel):
    minimum_field_accuracy: float | None = Field(default=None, ge=0, le=1)
    minimum_chunk_recall_at_k: float | None = Field(default=None, ge=0, le=1)
    minimum_citation_validity: float | None = Field(default=None, ge=0, le=1)
    minimum_pass_rate: float | None = Field(default=None, ge=0, le=1)
    maximum_latency_regression_percent: float | None = Field(default=None, ge=0)
    maximum_token_regression_percent: float | None = Field(default=None, ge=0)


class EvaluationComparisonRequest(ApiModel):
    run_a_id: str
    run_b_id: str
    thresholds: RegressionThresholds = Field(default_factory=RegressionThresholds)
    allow_incompatible_embeddings: bool = False


class MetricComparison(ApiModel):
    metric: str
    run_a: float | None
    run_b: float | None
    delta: float | None


class EvaluationComparisonResponse(ApiModel):
    run_a_id: str
    run_b_id: str
    dataset_id: str
    embedding_compatible: bool
    status: Literal["PASS", "WARNING", "REGRESSION"]
    metrics: list[MetricComparison]
    latency_regression_percent: float
    token_regression_percent: float
