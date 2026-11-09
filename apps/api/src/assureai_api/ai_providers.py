"""AI provider adapters for structured engineering-report extraction."""

import json
import re
import time
from typing import TYPE_CHECKING, Any

from assureai_api.ai_contracts import (
    AIProvider,
    EvidenceReference,
    InspectionExtractionOutput,
    ListExtraction,
    ProviderResult,
    ScalarExtraction,
    SourceChunk,
)

if TYPE_CHECKING:
    from assureai_api.config import Settings


class AIProviderError(RuntimeError):
    """A safe provider error suitable for extraction-run failure handling."""


class ProviderConfigurationError(AIProviderError):
    pass


def format_controlled_chunks(chunks: list[SourceChunk]) -> str:
    sections = []
    for chunk in chunks:
        page = str(chunk.page_number) if chunk.page_number is not None else "UNKNOWN"
        sections.append(f"CHUNK_ID: {chunk.id}\nPAGE: {page}\nTEXT:\n{chunk.content}")
    return "\n\n---\n\n".join(sections)


def _missing_scalar() -> ScalarExtraction:
    return ScalarExtraction(value=None, missing_reason="not_found", evidence=[])


def _missing_list() -> ListExtraction:
    return ListExtraction(value=None, missing_reason="not_found", evidence=[])


def _line_value(chunks: list[SourceChunk], label: str) -> tuple[str, EvidenceReference] | None:
    pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    for chunk in chunks:
        match = pattern.search(chunk.content)
        if match:
            quote = match.group(0).strip()
            return match.group(1).strip(), EvidenceReference(chunk_id=chunk.id, quote=quote)
    return None


def _scalar_from_line(chunks: list[SourceChunk], label: str) -> ScalarExtraction:
    found = _line_value(chunks, label)
    if found is None:
        return _missing_scalar()
    value, evidence = found
    return ScalarExtraction(value=value, missing_reason=None, evidence=[evidence])


def _document_type(chunks: list[SourceChunk]) -> ScalarExtraction:
    for chunk in chunks:
        for line in chunk.content.splitlines():
            candidate = line.strip()
            if "INSPECTION REPORT" in candidate.upper():
                return ScalarExtraction(
                    value=" ".join(candidate.split()),
                    missing_reason=None,
                    evidence=[EvidenceReference(chunk_id=chunk.id, quote=candidate)],
                )
    return _missing_scalar()


def _numbered_recommendations(chunks: list[SourceChunk]) -> ListExtraction:
    values: list[str] = []
    evidence: list[EvidenceReference] = []
    pattern = re.compile(r"(?ms)^\s*\d+\.\s+(.+?)(?=^\s*\d+\.|\n\s*\n|\Z)")
    for chunk in chunks:
        for match in pattern.finditer(chunk.content):
            raw = match.group(0).strip()
            value = " ".join(match.group(1).split())
            if value:
                values.append(value)
                evidence.append(EvidenceReference(chunk_id=chunk.id, quote=raw))
    if not values:
        return _missing_list()
    return ListExtraction(value=values, missing_reason=None, evidence=evidence)


def _identified_issues(chunks: list[SourceChunk]) -> ListExtraction:
    issue_terms = (" chip", " abrasion", " corrosion", " defect", " damage", " leakage")
    negative_terms = ("no active", "no laminate", "no leakage", "not sufficient to classify")
    values: list[str] = []
    evidence: list[EvidenceReference] = []
    for chunk in chunks:
        sentences = re.split(r"(?<=[.!?])\s+", chunk.content)
        for sentence in sentences:
            normalized = " ".join(sentence.split()).strip()
            lowered = f" {normalized.lower()}"
            if (
                normalized
                and any(term in lowered for term in issue_terms)
                and not any(term in lowered for term in negative_terms)
            ):
                values.append(normalized)
                evidence.append(EvidenceReference(chunk_id=chunk.id, quote=sentence.strip()))
    if not values:
        return _missing_list()
    return ListExtraction(value=values, missing_reason=None, evidence=evidence)


class DevelopmentAIProvider:
    """Deterministic, offline provider for development, tests, and demos."""

    provider_name = "development"
    model_name = "deterministic-development-v1"

    def extract_structured(
        self,
        *,
        prompt: str,
        chunks: list[SourceChunk],
    ) -> ProviderResult:
        started = time.perf_counter()
        output = InspectionExtractionOutput(
            asset_id=_scalar_from_line(chunks, "Asset ID"),
            document_type=_document_type(chunks),
            manufacturer=_scalar_from_line(chunks, "Manufacturer"),
            model=_scalar_from_line(chunks, "Model"),
            serial_number=_scalar_from_line(chunks, "Serial number"),
            inspection_date=_scalar_from_line(chunks, "Inspection date"),
            location=_scalar_from_line(chunks, "Location"),
            inspection_result=_scalar_from_line(chunks, "Inspection result"),
            identified_issues=_identified_issues(chunks),
            recommendations=_numbered_recommendations(chunks),
            inspector=_scalar_from_line(chunks, "Inspector"),
            next_inspection_date=_scalar_from_line(chunks, "Next inspection date"),
        )
        structured_data = output.model_dump(mode="json")
        input_text = prompt + format_controlled_chunks(chunks)
        output_text = json.dumps(structured_data, separators=(",", ":"))
        return ProviderResult(
            structured_data=structured_data,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=max(1, len(input_text) // 4),
            output_tokens=max(1, len(output_text) // 4),
        )


class OpenAIProvider:
    """OpenAI Responses API adapter using Pydantic structured outputs."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ProviderConfigurationError("OpenAI provider requires an API key.")
        from openai import OpenAI

        self.model_name = model
        self._client: Any = OpenAI(api_key=api_key)

    def extract_structured(
        self,
        *,
        prompt: str,
        chunks: list[SourceChunk],
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                input=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": format_controlled_chunks(chunks),
                    },
                ],
                text_format=InspectionExtractionOutput,
                store=False,
            )
        except Exception as exc:
            raise AIProviderError("OpenAI structured extraction request failed.") from exc

        parsed = response.output_parsed
        if response.status != "completed" or parsed is None:
            raise AIProviderError("OpenAI did not return a completed structured response.")
        usage = response.usage
        return ProviderResult(
            structured_data=parsed.model_dump(mode="json"),
            provider=self.provider_name,
            model=response.model or self.model_name,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=usage.input_tokens if usage is not None else None,
            output_tokens=usage.output_tokens if usage is not None else None,
        )


def create_ai_provider(settings: "Settings") -> AIProvider:
    if settings.ai_provider == "development":
        return DevelopmentAIProvider()
    if settings.ai_provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return OpenAIProvider(api_key=key, model=settings.openai_model)
    raise ProviderConfigurationError("AI extraction is disabled.")


def provider_identity(settings: "Settings") -> tuple[str, str]:
    if settings.ai_provider == "development":
        return DevelopmentAIProvider.provider_name, DevelopmentAIProvider.model_name
    if settings.ai_provider == "openai":
        return OpenAIProvider.provider_name, settings.openai_model
    return "disabled", "disabled"
