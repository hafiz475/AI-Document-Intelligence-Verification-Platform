"""Provider-neutral structured extraction contracts."""

from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, model_validator


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    quote: str


class ScalarExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None
    missing_reason: str | None
    evidence: list[EvidenceReference]

    @model_validator(mode="after")
    def validate_missing_state(self) -> Self:
        if self.value is None and not self.missing_reason:
            raise ValueError("missing_reason is required when value is null")
        if self.value is not None and self.missing_reason is not None:
            raise ValueError("missing_reason must be null when value is present")
        return self


class ListExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: list[str] | None
    missing_reason: str | None
    evidence: list[EvidenceReference]

    @model_validator(mode="after")
    def validate_missing_state(self) -> Self:
        if self.value is None and not self.missing_reason:
            raise ValueError("missing_reason is required when value is null")
        if self.value is not None and self.missing_reason is not None:
            raise ValueError("missing_reason must be null when value is present")
        if self.value == []:
            raise ValueError("use null with missing_reason instead of an empty list")
        return self


class InspectionExtractionOutput(BaseModel):
    """The only structured output accepted for engineering inspection extraction."""

    model_config = ConfigDict(extra="forbid")

    asset_id: ScalarExtraction
    document_type: ScalarExtraction
    manufacturer: ScalarExtraction
    model: ScalarExtraction
    serial_number: ScalarExtraction
    inspection_date: ScalarExtraction
    location: ScalarExtraction
    inspection_result: ScalarExtraction
    identified_issues: ListExtraction
    recommendations: ListExtraction
    inspector: ScalarExtraction
    next_inspection_date: ScalarExtraction


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structured_data: dict[str, Any]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class SourceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_number: int | None
    content: str


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def extract_structured(
        self,
        *,
        prompt: str,
        chunks: list[SourceChunk],
    ) -> ProviderResult: ...


FIELD_TYPES: dict[str, str] = {
    "asset_id": "string",
    "document_type": "string",
    "manufacturer": "string",
    "model": "string",
    "serial_number": "string",
    "inspection_date": "date",
    "location": "string",
    "inspection_result": "string",
    "identified_issues": "string_list",
    "recommendations": "string_list",
    "inspector": "string",
    "next_inspection_date": "date",
}


def normalize_value(value: str | list[str] | None) -> str | list[str] | None:
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    if isinstance(value, list):
        normalized_items = [" ".join(item.split()) for item in value]
        return [item for item in normalized_items if item] or None
    return None
