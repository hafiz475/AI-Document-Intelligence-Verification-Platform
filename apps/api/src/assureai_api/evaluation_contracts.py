"""Typed, versioned contracts for persisted evaluation cases."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from assureai_api.models import EvaluationType, RagSupportStatus


class EvaluationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceExpectation(EvaluationContract):
    chunk_id: str
    page_number: int | None = Field(default=None, ge=1)
    quote: str | None = Field(default=None, min_length=1)


class ExtractionCaseInput(EvaluationContract):
    document_id: str


class ExtractionCaseExpected(EvaluationContract):
    expected_fields: dict[str, Any] = Field(min_length=1)
    expected_evidence: dict[str, list[EvidenceExpectation]] = Field(default_factory=dict)


class RetrievalCaseInput(EvaluationContract):
    query: str = Field(min_length=1, max_length=4000)
    document_id: str | None = None


class RetrievalCaseExpected(EvaluationContract):
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_document_ids: list[str] = Field(default_factory=list)
    maximum_first_relevant_rank: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def require_relevance_target(self) -> "RetrievalCaseExpected":
        if not self.expected_chunk_ids and not self.expected_document_ids:
            raise ValueError("At least one expected chunk or document is required.")
        return self


class RagCaseInput(EvaluationContract):
    question: str = Field(min_length=1, max_length=4000)
    document_id: str | None = None


class RagCaseExpected(EvaluationContract):
    support_status: RagSupportStatus
    required_citation_chunk_ids: list[str] = Field(default_factory=list)
    forbidden_citation_chunk_ids: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)


CaseContract = (
    ExtractionCaseInput
    | ExtractionCaseExpected
    | RetrievalCaseInput
    | RetrievalCaseExpected
    | RagCaseInput
    | RagCaseExpected
)


def validate_case_contracts(
    evaluation_type: EvaluationType,
    input_json: dict[str, Any],
    expected_json: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and canonicalize case JSON for the owning dataset type."""

    contract: tuple[type[EvaluationContract], type[EvaluationContract]]
    if evaluation_type == EvaluationType.EXTRACTION:
        contract = (ExtractionCaseInput, ExtractionCaseExpected)
    elif evaluation_type == EvaluationType.RETRIEVAL:
        contract = (RetrievalCaseInput, RetrievalCaseExpected)
    else:
        contract = (RagCaseInput, RagCaseExpected)
    validated_input = contract[0].model_validate(input_json)
    validated_expected = contract[1].model_validate(expected_json)
    return validated_input.model_dump(mode="json"), validated_expected.model_dump(mode="json")
