"""Application services for structured AI extraction and human review."""

import logging
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from assureai_api.ai_contracts import (
    FIELD_TYPES,
    AIProvider,
    InspectionExtractionOutput,
    SourceChunk,
    normalize_value,
)
from assureai_api.ai_providers import AIProviderError, provider_identity
from assureai_api.config import Settings
from assureai_api.models import (
    AuditEvent,
    DocumentChunk,
    DocumentStatus,
    ExtractedField,
    ExtractionEvidence,
    ExtractionRun,
    ExtractionRunStatus,
    ReviewStatus,
    SupportStatus,
    utc_now,
)
from assureai_api.prompts import ensure_inspection_prompt_v1
from assureai_api.services import NotFoundError, get_document

logger = logging.getLogger(__name__)


class ExtractionConflictError(ValueError):
    pass


class ExtractionUnavailableError(RuntimeError):
    pass


class StructuredOutputError(RuntimeError):
    pass


def _audit(
    session: Session,
    *,
    run: ExtractionRun,
    event_type: str,
    field_id: str | None = None,
    reviewer: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            project_id=run.project_id,
            document_id=run.document_id,
            extraction_run_id=run.id,
            extracted_field_id=field_id,
            event_type=event_type,
            event_metadata=metadata or {},
            reviewer=reviewer,
        )
    )


def create_extraction_run(
    session: Session,
    *,
    settings: Settings,
    enqueue: Callable[[str], object],
    project_id: str,
    document_id: str,
) -> ExtractionRun:
    document = get_document(session, project_id, document_id)
    if document.status != DocumentStatus.READY:
        raise ExtractionConflictError("Document must be READY before AI extraction.")
    if settings.ai_provider == "disabled":
        raise ExtractionUnavailableError("AI extraction is disabled by configuration.")

    prompt_version = ensure_inspection_prompt_v1(session)
    provider, model = provider_identity(settings)
    run = ExtractionRun(
        project_id=project_id,
        document_id=document_id,
        status=ExtractionRunStatus.QUEUED,
        provider=provider,
        model=model,
        prompt_version_id=prompt_version.id,
    )
    session.add(run)
    session.flush()
    _audit(session, run=run, event_type="extraction.created")
    session.commit()
    logger.info(
        "extraction_created",
        extra={"project_id": project_id, "document_id": document_id, "extraction_run_id": run.id},
    )

    try:
        enqueue(run.id)
    except Exception as exc:
        run.status = ExtractionRunStatus.FAILED
        run.completed_at = utc_now()
        run.error_code = "QUEUE_ERROR"
        run.error_message = "Extraction could not be queued."
        _audit(session, run=run, event_type="extraction.failed", metadata={"code": "QUEUE_ERROR"})
        session.commit()
        logger.exception(
            "extraction_failed",
            extra={
                "project_id": project_id,
                "document_id": document_id,
                "extraction_run_id": run.id,
                "error_code": "QUEUE_ERROR",
            },
        )
        raise ExtractionUnavailableError("Extraction could not be queued.") from exc
    session.refresh(run)
    return run


def _run_query() -> Select[ExtractionRun]:
    return select(ExtractionRun).options(
        selectinload(ExtractionRun.prompt_version),
        selectinload(ExtractionRun.fields).selectinload(ExtractedField.evidence),
        selectinload(ExtractionRun.audit_events),
    )


def list_extraction_runs(
    session: Session, project_id: str, document_id: str
) -> list[ExtractionRun]:
    get_document(session, project_id, document_id)
    statement = (
        _run_query()
        .where(
            ExtractionRun.project_id == project_id,
            ExtractionRun.document_id == document_id,
        )
        .order_by(ExtractionRun.created_at.desc())
    )
    return list(session.scalars(statement).unique())


def get_extraction_run(
    session: Session, project_id: str, document_id: str, run_id: str
) -> ExtractionRun:
    get_document(session, project_id, document_id)
    statement = _run_query().where(
        ExtractionRun.id == run_id,
        ExtractionRun.project_id == project_id,
        ExtractionRun.document_id == document_id,
    )
    run = session.scalar(statement)
    if run is None:
        raise NotFoundError("Extraction run not found in this project and document.")
    return run


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _evidence_is_valid(
    *,
    chunk: DocumentChunk,
    quote: str,
    page_count: int | None,
) -> bool:
    if not quote.strip():
        return False
    if chunk.page_number is not None:
        if chunk.page_number < 1:
            return False
        if page_count is not None and chunk.page_number > page_count:
            return False
    return _normalized_text(quote) in _normalized_text(chunk.content)


def _support_status(reference_count: int, valid_count: int) -> SupportStatus:
    if valid_count == 0:
        return SupportStatus.UNSUPPORTED
    if valid_count == reference_count:
        return SupportStatus.SUPPORTED
    return SupportStatus.PARTIALLY_SUPPORTED


def process_extraction_run(
    session: Session,
    *,
    provider: AIProvider,
    run_id: str,
) -> None:
    run = session.get(ExtractionRun, run_id)
    if run is None:
        logger.warning("extraction_missing", extra={"extraction_run_id": run_id})
        return
    if run.status == ExtractionRunStatus.COMPLETED:
        return

    run.status = ExtractionRunStatus.PROCESSING
    run.started_at = utc_now()
    run.completed_at = None
    run.error_code = None
    run.error_message = None
    _audit(session, run=run, event_type="extraction.started")
    session.commit()
    logger.info(
        "extraction_started",
        extra={
            "project_id": run.project_id,
            "document_id": run.document_id,
            "extraction_run_id": run.id,
        },
    )

    try:
        run = session.get(ExtractionRun, run_id)
        if run is None:
            return
        chunks = list(
            session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == run.document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
        if not chunks:
            raise StructuredOutputError("Document has no chunks to extract.")
        prompt_version = ensure_inspection_prompt_v1(session)
        if run.prompt_version_id != prompt_version.id:
            prompt_version = run.prompt_version

        source_chunks = [
            SourceChunk(id=chunk.id, page_number=chunk.page_number, content=chunk.content)
            for chunk in chunks
        ]
        logger.info(
            "provider_request_started",
            extra={
                "project_id": run.project_id,
                "document_id": run.document_id,
                "extraction_run_id": run.id,
                "provider": run.provider,
                "model": run.model,
            },
        )
        result = provider.extract_structured(prompt=prompt_version.content, chunks=source_chunks)
        logger.info(
            "provider_request_completed",
            extra={
                "project_id": run.project_id,
                "document_id": run.document_id,
                "extraction_run_id": run.id,
                "provider": result.provider,
                "model": result.model,
                "latency_ms": result.latency_ms,
            },
        )
        try:
            output = InspectionExtractionOutput.model_validate(result.structured_data)
        except ValidationError as exc:
            raise StructuredOutputError("Provider returned invalid structured data.") from exc

        existing_fields = list(
            session.scalars(
                select(ExtractedField)
                .options(selectinload(ExtractedField.evidence))
                .where(ExtractedField.extraction_run_id == run.id)
            )
        )
        for existing in existing_fields:
            session.delete(existing)
        session.flush()

        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        document = run.document
        for field_name, field_type in FIELD_TYPES.items():
            extracted = getattr(output, field_name)
            valid_references: list[tuple[DocumentChunk, str]] = []
            seen: set[tuple[str, str]] = set()
            for reference in extracted.evidence:
                chunk = chunk_by_id.get(reference.chunk_id)
                key = (reference.chunk_id, reference.quote)
                if (
                    chunk is not None
                    and key not in seen
                    and _evidence_is_valid(
                        chunk=chunk,
                        quote=reference.quote,
                        page_count=document.page_count,
                    )
                ):
                    seen.add(key)
                    valid_references.append((chunk, reference.quote.strip()))

            support_status = _support_status(len(extracted.evidence), len(valid_references))
            field = ExtractedField(
                extraction_run_id=run.id,
                document_id=run.document_id,
                field_name=field_name,
                field_type=field_type,
                raw_value=extracted.value,
                normalized_value=normalize_value(extracted.value),
                missing_reason=extracted.missing_reason,
                review_status=ReviewStatus.UNREVIEWED,
                support_status=support_status,
            )
            session.add(field)
            session.flush()
            for chunk, quote in valid_references:
                session.add(
                    ExtractionEvidence(
                        extracted_field_id=field.id,
                        document_chunk_id=chunk.id,
                        page_number=chunk.page_number,
                        quote=quote,
                    )
                )

        run.status = ExtractionRunStatus.COMPLETED
        run.completed_at = utc_now()
        run.provider = result.provider
        run.model = result.model
        run.latency_ms = result.latency_ms
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        _audit(
            session,
            run=run,
            event_type="extraction.completed",
            metadata={"field_count": len(FIELD_TYPES)},
        )
        session.commit()
        logger.info(
            "extraction_completed",
            extra={
                "project_id": run.project_id,
                "document_id": run.document_id,
                "extraction_run_id": run.id,
                "latency_ms": run.latency_ms,
            },
        )
    except Exception as exc:
        session.rollback()
        failed_run = session.get(ExtractionRun, run_id)
        if failed_run is not None:
            if isinstance(exc, StructuredOutputError):
                code = "STRUCTURED_OUTPUT_INVALID"
                message = str(exc)
            elif isinstance(exc, AIProviderError):
                code = "PROVIDER_ERROR"
                message = str(exc)
            else:
                code = "EXTRACTION_ERROR"
                message = "Structured extraction failed."
            failed_run.status = ExtractionRunStatus.FAILED
            failed_run.completed_at = utc_now()
            failed_run.error_code = code
            failed_run.error_message = message
            _audit(
                session,
                run=failed_run,
                event_type="extraction.failed",
                metadata={"code": code},
            )
            session.commit()
            logger.exception(
                "extraction_failed",
                extra={
                    "project_id": failed_run.project_id,
                    "document_id": failed_run.document_id,
                    "extraction_run_id": failed_run.id,
                    "error_code": code,
                },
            )
        raise


def review_extracted_field(
    session: Session,
    *,
    project_id: str,
    document_id: str,
    run_id: str,
    field_id: str,
    decision: ReviewStatus,
    value: str | list[str] | None,
    reason: str | None,
) -> ExtractedField:
    run = get_extraction_run(session, project_id, document_id, run_id)
    if run.status != ExtractionRunStatus.COMPLETED:
        raise ExtractionConflictError("Only completed extractions can be reviewed.")
    field = session.scalar(
        select(ExtractedField)
        .options(selectinload(ExtractedField.evidence))
        .where(
            ExtractedField.id == field_id,
            ExtractedField.extraction_run_id == run_id,
            ExtractedField.document_id == document_id,
        )
    )
    if field is None:
        raise NotFoundError("Extracted field not found in this extraction run.")
    if field.review_status != ReviewStatus.UNREVIEWED:
        raise ExtractionConflictError("This field has already been reviewed.")
    if decision == ReviewStatus.UNREVIEWED:
        raise ExtractionConflictError("UNREVIEWED is not a review decision.")
    if decision == ReviewStatus.CORRECTED and value is None:
        raise ExtractionConflictError("A corrected value is required.")
    if decision in {ReviewStatus.CORRECTED, ReviewStatus.REJECTED} and not reason:
        raise ExtractionConflictError("A review reason is required.")

    field.review_status = decision
    field.corrected_value = normalize_value(value) if decision == ReviewStatus.CORRECTED else None
    field.review_reason = reason.strip() if reason else None
    field.reviewer = None
    field.reviewed_at = utc_now()
    event_type = {
        ReviewStatus.VERIFIED: "field.verified",
        ReviewStatus.CORRECTED: "field.corrected",
        ReviewStatus.REJECTED: "field.rejected",
    }[decision]
    _audit(
        session,
        run=run,
        event_type=event_type,
        field_id=field.id,
        metadata={"field_name": field.field_name},
    )
    session.commit()
    session.refresh(field)
    logger.info(
        "field_reviewed",
        extra={
            "project_id": project_id,
            "document_id": document_id,
            "extraction_run_id": run_id,
            "field_id": field.id,
            "decision": decision.value,
        },
    )
    return field
