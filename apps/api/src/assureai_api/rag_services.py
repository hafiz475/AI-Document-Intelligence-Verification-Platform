"""Application orchestration for retrieval-augmented, citation-validated answers."""

import logging
import time
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session, selectinload

from assureai_api.config import Settings
from assureai_api.embedding_contracts import EmbeddingProvider
from assureai_api.models import (
    AuditEvent,
    Document,
    DocumentChunk,
    QuestionRetrievedChunk,
    RagAnswer,
    RagCitation,
    RagQuestion,
    RagQuestionStatus,
    RagSupportStatus,
    utc_now,
)
from assureai_api.observability import provider_metrics, trace_id
from assureai_api.prompts import ensure_rag_prompt_v1, get_prompt_version
from assureai_api.rag_contracts import (
    RagAnswerOutput,
    RagAnswerProvider,
    RagCitationReference,
    RagContextChunk,
)
from assureai_api.rag_providers import (
    INSUFFICIENT_ANSWER,
    RagProviderError,
    rag_provider_identity,
)
from assureai_api.retrieval_services import RetrievalUnavailableError, semantic_search
from assureai_api.services import NotFoundError, get_document, get_project

logger = logging.getLogger(__name__)


class RagUnavailableError(RuntimeError):
    pass


class RagStructuredOutputError(RuntimeError):
    pass


class CitationValidationError(RuntimeError):
    pass


def _audit(
    session: Session,
    *,
    question: RagQuestion,
    event_type: str,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            project_id=question.project_id,
            document_id=question.document_id,
            rag_question_id=question.id,
            event_type=event_type,
            event_metadata=metadata or {},
            trace_id=trace_id(),
            target_type="rag_question",
            target_id=question.id,
        )
    )


def create_rag_question(
    session: Session,
    *,
    settings: Settings,
    enqueue: Callable[[str], object],
    project_id: str,
    document_id: str | None,
    question_text: str,
    top_k: int,
    prompt_version_id: str | None = None,
) -> RagQuestion:
    get_project(session, project_id)
    if document_id is not None:
        get_document(session, project_id, document_id)
    if settings.embedding_provider == "disabled":
        raise RagUnavailableError("Question answering requires configured embeddings.")
    if settings.ai_provider == "disabled":
        raise RagUnavailableError("RAG answer generation is disabled by configuration.")

    provider, model = rag_provider_identity(settings)
    default_prompt = ensure_rag_prompt_v1(session)
    prompt_version = (
        get_prompt_version(session, prompt_version_id) if prompt_version_id else default_prompt
    )
    if (
        prompt_version is None
        or prompt_version.prompt_template_id != default_prompt.prompt_template_id
    ):
        raise RagUnavailableError("Prompt version is not a RAG answer prompt.")
    question = RagQuestion(
        project_id=project_id,
        document_id=document_id,
        question=question_text,
        status=RagQuestionStatus.QUEUED,
        retrieval_top_k=top_k,
        provider=provider,
        model=model,
        prompt_version_id=prompt_version.id,
    )
    session.add(question)
    session.flush()
    _audit(session, question=question, event_type="rag.question_created")
    session.commit()
    logger.info(
        "rag.question_created",
        extra={
            "project_id": project_id,
            "question_id": question.id,
            "document_id": document_id,
            "provider": provider,
            "model": model,
        },
    )
    try:
        enqueue(question.id)
    except Exception as exc:
        question.status = RagQuestionStatus.FAILED
        question.completed_at = utc_now()
        question.error_message = "Question processing could not be queued."
        _audit(
            session,
            question=question,
            event_type="rag.answer_failed",
            metadata={"code": "QUEUE_ERROR"},
        )
        session.commit()
        raise RagUnavailableError(question.error_message) from exc
    return get_rag_question(session, project_id, question.id)


def _question_query() -> Select[RagQuestion]:
    return select(RagQuestion).options(
        selectinload(RagQuestion.prompt_version),
        selectinload(RagQuestion.retrieved_chunks).selectinload(QuestionRetrievedChunk.chunk),
        selectinload(RagQuestion.retrieved_chunks).selectinload(QuestionRetrievedChunk.document),
        selectinload(RagQuestion.answer)
        .selectinload(RagAnswer.citations)
        .selectinload(RagCitation.document),
        selectinload(RagQuestion.audit_events),
    )


def get_rag_question(session: Session, project_id: str, question_id: str) -> RagQuestion:
    get_project(session, project_id)
    question = session.scalar(
        _question_query().where(
            RagQuestion.id == question_id,
            RagQuestion.project_id == project_id,
        )
    )
    if question is None:
        raise NotFoundError("Question not found in this project.")
    return question


def list_rag_questions(
    session: Session,
    project_id: str,
    *,
    document_id: str | None = None,
) -> list[RagQuestion]:
    get_project(session, project_id)
    if document_id is not None:
        get_document(session, project_id, document_id)
    query = _question_query().where(RagQuestion.project_id == project_id)
    if document_id is not None:
        query = query.where(RagQuestion.document_id == document_id)
    return list(session.scalars(query.order_by(RagQuestion.created_at.desc())))


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def validate_rag_answer(
    session: Session,
    *,
    question: RagQuestion,
    output: RagAnswerOutput,
) -> list[tuple[RagCitationReference, QuestionRetrievedChunk]]:
    if (
        output.support_status
        in {
            RagSupportStatus.SUPPORTED,
            RagSupportStatus.PARTIALLY_SUPPORTED,
        }
        and not output.citations
    ):
        raise CitationValidationError(f"{output.support_status.value} requires a valid citation.")
    if output.support_status == RagSupportStatus.INSUFFICIENT_EVIDENCE and output.citations:
        raise CitationValidationError("INSUFFICIENT_EVIDENCE must not include citations.")

    retrieved = {item.chunk_id: item for item in question.retrieved_chunks}
    validated: list[tuple[RagCitationReference, QuestionRetrievedChunk]] = []
    seen: set[tuple[str, str]] = set()
    for citation in output.citations:
        chunk = session.get(DocumentChunk, citation.chunk_id)
        if chunk is None:
            raise CitationValidationError("Citation references an unknown chunk.")
        document = session.get(Document, chunk.document_id)
        if document is None or document.project_id != question.project_id:
            raise CitationValidationError("Citation crosses the project evidence boundary.")
        provenance = retrieved.get(citation.chunk_id)
        if provenance is None:
            raise CitationValidationError("Citation references a chunk that was not retrieved.")
        if provenance.document_id != chunk.document_id:
            raise CitationValidationError("Persisted retrieval provenance is inconsistent.")
        if citation.document_id != chunk.document_id:
            raise CitationValidationError("Citation document does not match its chunk.")
        if citation.page_number != chunk.page_number:
            raise CitationValidationError("Citation page does not match its chunk.")
        normalized_quote = _normalize_whitespace(citation.quote)
        if not normalized_quote or normalized_quote not in _normalize_whitespace(chunk.content):
            raise CitationValidationError("Citation quote is not present in its chunk.")
        identity = (citation.chunk_id, normalized_quote)
        if identity in seen:
            raise CitationValidationError("Duplicate citations are not accepted.")
        seen.add(identity)
        validated.append((citation, provenance))
    return validated


def _safe_failure_message(exc: Exception) -> str:
    if isinstance(
        exc,
        (
            CitationValidationError,
            RagProviderError,
            RagStructuredOutputError,
            RetrievalUnavailableError,
        ),
    ):
        return str(exc)
    return "Question processing failed."


def process_rag_question(
    session: Session,
    *,
    embedding_provider: EmbeddingProvider,
    answer_provider: RagAnswerProvider,
    question_id: str,
) -> None:
    question = session.get(RagQuestion, question_id)
    if question is None:
        logger.warning("rag.question_missing", extra={"question_id": question_id})
        return
    if question.status == RagQuestionStatus.COMPLETED:
        return

    question.status = RagQuestionStatus.PROCESSING
    question.started_at = utc_now()
    question.completed_at = None
    question.error_message = None
    session.execute(
        delete(QuestionRetrievedChunk).where(QuestionRetrievedChunk.question_id == question.id)
    )
    session.commit()
    started = time.perf_counter()
    logger.info(
        "rag.retrieval_started",
        extra={
            "project_id": question.project_id,
            "question_id": question.id,
            "document_id": question.document_id,
            "provider": embedding_provider.provider_name,
            "model": embedding_provider.model_name,
        },
    )
    try:
        search = semantic_search(
            session,
            provider=embedding_provider,
            project_id=question.project_id,
            document_id=question.document_id,
            query=question.question,
            top_k=question.retrieval_top_k,
        )
        for search_item in search.results:
            session.add(
                QuestionRetrievedChunk(
                    question_id=question.id,
                    chunk_id=search_item.chunk_id,
                    document_id=search_item.document_id,
                    rank=search_item.rank,
                    similarity_score=search_item.similarity_score,
                    embedding_provider=search.provider,
                    embedding_model=search.model,
                )
            )
        _audit(
            session,
            question=question,
            event_type="rag.retrieval_completed",
            metadata={"retrieval_count": len(search.results)},
        )
        session.commit()
        logger.info(
            "rag.retrieval_completed",
            extra={
                "project_id": question.project_id,
                "question_id": question.id,
                "document_id": question.document_id,
                "retrieval_count": len(search.results),
                "provider": search.provider,
                "model": search.model,
            },
        )

        question = get_rag_question(session, question.project_id, question.id)
        context = [
            RagContextChunk(
                rank=item.rank,
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_name=item.document.original_filename,
                page_number=item.chunk.page_number,
                similarity_score=item.similarity_score,
                content=item.chunk.content,
            )
            for item in sorted(question.retrieved_chunks, key=lambda item: item.rank)
        ]
        logger.info(
            "rag.generation_started",
            extra={
                "project_id": question.project_id,
                "question_id": question.id,
                "document_id": question.document_id,
                "retrieval_count": len(context),
                "provider": question.provider,
                "model": question.model,
            },
        )
        if not context:
            output = RagAnswerOutput(
                answer=INSUFFICIENT_ANSWER,
                support_status=RagSupportStatus.INSUFFICIENT_EVIDENCE,
                citations=[],
            )
            provider_latency = 0
            input_tokens = None
            output_tokens = None
        else:
            with provider_metrics(answer_provider.provider_name, "rag_answer"):
                provider_result = answer_provider.generate_answer(
                    prompt=question.prompt_version.content,
                    question=question.question,
                    context=context,
                )
            if (
                provider_result.provider != question.provider
                or provider_result.model != question.model
                or answer_provider.provider_name != question.provider
            ):
                raise RagProviderError("Worker RAG provider configuration does not match the run.")
            try:
                output = RagAnswerOutput.model_validate(provider_result.structured_data)
            except ValidationError as exc:
                raise RagStructuredOutputError(
                    "RAG provider returned invalid structured output."
                ) from exc
            provider_latency = provider_result.latency_ms
            input_tokens = provider_result.input_tokens
            output_tokens = provider_result.output_tokens

        validated = validate_rag_answer(session, question=question, output=output)
        answer_text = (
            INSUFFICIENT_ANSWER
            if output.support_status == RagSupportStatus.INSUFFICIENT_EVIDENCE
            else output.answer.strip()
        )
        answer = RagAnswer(
            question_id=question.id,
            answer_text=answer_text,
            support_status=output.support_status,
            confidence=None,
        )
        session.add(answer)
        session.flush()
        for citation, provenance in validated:
            session.add(
                RagCitation(
                    answer_id=answer.id,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    page_number=citation.page_number,
                    quote=_normalize_whitespace(citation.quote),
                    rank=provenance.rank,
                    similarity_score=provenance.similarity_score,
                )
            )
        question.status = RagQuestionStatus.COMPLETED
        question.completed_at = utc_now()
        question.latency_ms = max(provider_latency, round((time.perf_counter() - started) * 1000))
        question.input_tokens = input_tokens
        question.output_tokens = output_tokens
        question.total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        _audit(
            session,
            question=question,
            event_type="rag.answer_completed",
            metadata={
                "support_status": output.support_status.value,
                "citation_count": len(validated),
            },
        )
        session.commit()
        logger.info(
            "rag.generation_completed",
            extra={
                "project_id": question.project_id,
                "question_id": question.id,
                "document_id": question.document_id,
                "retrieval_count": len(context),
                "provider": question.provider,
                "model": question.model,
                "latency_ms": question.latency_ms,
            },
        )
    except Exception as exc:
        session.rollback()
        failed = session.get(RagQuestion, question_id)
        if failed is not None:
            failed.status = RagQuestionStatus.FAILED
            failed.completed_at = utc_now()
            failed.latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            failed.error_message = _safe_failure_message(exc)
            if isinstance(exc, CitationValidationError):
                _audit(
                    session,
                    question=failed,
                    event_type="rag.citation_rejected",
                    metadata={"reason": str(exc)},
                )
                logger.warning(
                    "rag.citation_validation_failed",
                    extra={
                        "project_id": failed.project_id,
                        "question_id": failed.id,
                        "document_id": failed.document_id,
                        "provider": failed.provider,
                        "model": failed.model,
                    },
                )
            _audit(
                session,
                question=failed,
                event_type="rag.answer_failed",
                metadata={"error_type": type(exc).__name__},
            )
            session.commit()
            logger.exception(
                "rag.failed",
                extra={
                    "project_id": failed.project_id,
                    "question_id": failed.id,
                    "document_id": failed.document_id,
                    "provider": failed.provider,
                    "model": failed.model,
                    "latency_ms": failed.latency_ms,
                },
            )
        raise
