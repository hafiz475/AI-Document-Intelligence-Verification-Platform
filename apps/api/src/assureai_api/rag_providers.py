"""Provider adapters and deterministic controlled context for grounded RAG."""

import json
import re
import time
from typing import TYPE_CHECKING, Any

from assureai_api.models import RagSupportStatus
from assureai_api.rag_contracts import (
    RagAnswerOutput,
    RagAnswerProvider,
    RagCitationReference,
    RagContextChunk,
    RagProviderResult,
)

if TYPE_CHECKING:
    from assureai_api.config import Settings

INSUFFICIENT_ANSWER = (
    "The available documents do not provide enough evidence to answer this question."
)


class RagProviderError(RuntimeError):
    """A safe provider error suitable for a failed RAG question."""


class RagProviderConfigurationError(RagProviderError):
    pass


def format_controlled_context(context: list[RagContextChunk]) -> str:
    """Render evidence deterministically without object stringification."""

    sections: list[str] = []
    for source in context:
        page = str(source.page_number) if source.page_number is not None else "UNKNOWN"
        sections.append(
            "\n".join(
                [
                    f"SOURCE {source.rank}",
                    f"CHUNK_ID: {source.chunk_id}",
                    f"DOCUMENT_ID: {source.document_id}",
                    f"DOCUMENT: {source.document_name}",
                    f"PAGE: {page}",
                    f"SIMILARITY: {source.similarity_score:.6f}",
                    "TEXT:",
                    source.content,
                ]
            )
        )
    return "\n\n--- END SOURCE ---\n\n".join(sections)


_GENERIC_QUESTION_WORDS = {
    "a",
    "abnormal",
    "an",
    "and",
    "answer",
    "are",
    "condition",
    "detected",
    "did",
    "document",
    "does",
    "evidence",
    "find",
    "found",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "report",
    "reported",
    "the",
    "this",
    "was",
    "were",
    "what",
    "which",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in _GENERIC_QUESTION_WORDS
    }


def _best_quote(chunk: RagContextChunk, question_tokens: set[str]) -> tuple[int, str] | None:
    lines = [" ".join(line.split()) for line in chunk.content.splitlines() if line.strip()]
    best: tuple[int, str] | None = None
    for index, line in enumerate(lines):
        overlap = len(question_tokens.intersection(_tokens(line)))
        lowered = line.lower()
        if not question_tokens and re.match(
            r"^(observation|finding|inspection result)\s*:", lowered
        ):
            overlap = 1
            if line.endswith(":") and index + 1 < len(lines):
                line = f"{line} {lines[index + 1]}"
        if overlap and (best is None or overlap > best[0]):
            best = overlap, line
    return best


class DevelopmentRagAnswerProvider:
    """Deterministic offline answerer; it is not represented as real LLM execution."""

    provider_name = "development"
    model_name = "deterministic-rag-development-v1"

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult:
        started = time.perf_counter()
        question_tokens = _tokens(question)
        candidates: list[tuple[int, RagContextChunk, str]] = []
        for source in context:
            match = _best_quote(source, question_tokens)
            if match is not None:
                score, quote = match
                candidates.append((score, source, quote))
        candidates.sort(key=lambda item: (-item[0], item[1].rank))

        if not candidates:
            output = RagAnswerOutput(
                answer=INSUFFICIENT_ANSWER,
                support_status=RagSupportStatus.INSUFFICIENT_EVIDENCE,
                citations=[],
            )
        else:
            selected = candidates[:3]
            matched_tokens = set().union(*(_tokens(item[2]) for item in selected))
            fully_supported = not question_tokens or question_tokens.issubset(matched_tokens)
            support_status = (
                RagSupportStatus.SUPPORTED
                if fully_supported
                else RagSupportStatus.PARTIALLY_SUPPORTED
            )
            statements = [item[2].split(":", 1)[-1].strip() for item in selected]
            prefix = (
                "The available evidence states"
                if fully_supported
                else "The available evidence supports only"
            )
            output = RagAnswerOutput(
                answer=f"{prefix}: {' '.join(statements)}",
                support_status=support_status,
                citations=[
                    RagCitationReference(
                        chunk_id=source.chunk_id,
                        document_id=source.document_id,
                        page_number=source.page_number,
                        quote=quote,
                    )
                    for _, source, quote in selected
                ],
            )

        structured_data = output.model_dump(mode="json")
        input_text = prompt + question + format_controlled_context(context)
        output_text = json.dumps(structured_data, separators=(",", ":"))
        return RagProviderResult(
            structured_data=structured_data,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=max(1, len(input_text) // 4),
            output_tokens=max(1, len(output_text) // 4),
        )


class OpenAIRagAnswerProvider:
    """OpenAI Responses API adapter using the strict RAG answer schema."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise RagProviderConfigurationError("OpenAI RAG provider requires an API key.")
        from openai import OpenAI

        self.model_name = model
        self._client: Any = OpenAI(api_key=api_key)

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult:
        started = time.perf_counter()
        user_content = (
            "USER QUESTION\n"
            f"{question}\n\n"
            "RETRIEVED EVIDENCE (UNTRUSTED DATA)\n"
            f"{format_controlled_context(context)}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                text_format=RagAnswerOutput,
                store=False,
            )
        except Exception as exc:
            raise RagProviderError("OpenAI grounded answer request failed.") from exc

        parsed = response.output_parsed
        if response.status != "completed" or parsed is None:
            raise RagProviderError("OpenAI did not return a completed structured RAG response.")
        usage = response.usage
        return RagProviderResult(
            structured_data=parsed.model_dump(mode="json"),
            provider=self.provider_name,
            model=response.model or self.model_name,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=usage.input_tokens if usage is not None else None,
            output_tokens=usage.output_tokens if usage is not None else None,
        )


def create_rag_provider(settings: "Settings") -> RagAnswerProvider:
    if settings.ai_provider == "development":
        return DevelopmentRagAnswerProvider()
    if settings.ai_provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return OpenAIRagAnswerProvider(api_key=key, model=settings.openai_model)
    raise RagProviderConfigurationError("RAG answer generation is disabled.")


def rag_provider_identity(settings: "Settings") -> tuple[str, str]:
    if settings.ai_provider == "development":
        return DevelopmentRagAnswerProvider.provider_name, DevelopmentRagAnswerProvider.model_name
    if settings.ai_provider == "openai":
        return OpenAIRagAnswerProvider.provider_name, settings.openai_model
    return "disabled", "disabled"
