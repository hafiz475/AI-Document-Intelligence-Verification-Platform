"""Bounded, project-scoped read models for product dashboards and reports."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from assureai_api.models import (
    AuditEvent,
    Document,
    DocumentStatus,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationType,
    ExtractedField,
    ExtractionRun,
    Project,
    RagAnswer,
    RagQuestion,
    RagSupportStatus,
    ReviewStatus,
    User,
)
from assureai_api.product_schemas import (
    ActivityItem,
    AuditIndexResponse,
    AuditItem,
    DocumentIndexResponse,
    OverviewMetrics,
    ProjectOverviewResponse,
    ProviderUsage,
    ReviewQueueItem,
    ReviewQueueResponse,
    UsageSummary,
)
from assureai_api.schemas import DocumentResponse, ExtractedFieldResponse
from assureai_api.services import NotFoundError


def _require_project(session: Session, project_id: str) -> None:
    if session.get(Project, project_id) is None:
        raise NotFoundError("Project not found.")


def _count(session: Session, statement: Select[Any]) -> int:
    value = cast(int | None, session.scalar(statement))
    return int(value or 0)


def _token_sum(session: Session, model: type[Any], project_id: str) -> tuple[int | None, int]:
    total, records = session.execute(
        select(func.sum(model.total_tokens), func.count(model.total_tokens)).where(
            model.project_id == project_id
        )
    ).one()
    typed_total = cast(int | None, total)
    typed_records = cast(int | None, records)
    return (int(typed_total) if typed_total is not None else None, int(typed_records or 0))


def _extraction_token_sum(session: Session, project_id: str) -> tuple[int | None, int]:
    token_expression = ExtractionRun.input_tokens + ExtractionRun.output_tokens
    total, records = session.execute(
        select(func.sum(token_expression), func.count(token_expression)).where(
            ExtractionRun.project_id == project_id
        )
    ).one()
    return (int(total) if total is not None else None, int(records or 0))


def get_project_overview(session: Session, project_id: str) -> ProjectOverviewResponse:
    _require_project(session, project_id)
    documents = _count(
        session, select(func.count(Document.id)).where(Document.project_id == project_id)
    )
    ready = _count(
        session,
        select(func.count(Document.id)).where(
            Document.project_id == project_id, Document.status == DocumentStatus.READY
        ),
    )
    failed = _count(
        session,
        select(func.count(Document.id)).where(
            Document.project_id == project_id, Document.status == DocumentStatus.FAILED
        ),
    )
    extraction_runs = _count(
        session,
        select(func.count(ExtractionRun.id)).where(ExtractionRun.project_id == project_id),
    )
    awaiting = _count(
        session,
        select(func.count(ExtractedField.id))
        .join(ExtractionRun, ExtractionRun.id == ExtractedField.extraction_run_id)
        .where(
            ExtractionRun.project_id == project_id,
            ExtractedField.review_status == ReviewStatus.UNREVIEWED,
        ),
    )
    verified = _count(
        session,
        select(func.count(ExtractedField.id))
        .join(ExtractionRun, ExtractionRun.id == ExtractedField.extraction_run_id)
        .where(
            ExtractionRun.project_id == project_id,
            ExtractedField.review_status == ReviewStatus.VERIFIED,
        ),
    )
    questions = _count(
        session, select(func.count(RagQuestion.id)).where(RagQuestion.project_id == project_id)
    )
    supported = _count(
        session,
        select(func.count(RagAnswer.id))
        .join(RagQuestion, RagQuestion.id == RagAnswer.question_id)
        .where(
            RagQuestion.project_id == project_id,
            RagAnswer.support_status == RagSupportStatus.SUPPORTED,
        ),
    )
    insufficient = _count(
        session,
        select(func.count(RagAnswer.id))
        .join(RagQuestion, RagQuestion.id == RagAnswer.question_id)
        .where(
            RagQuestion.project_id == project_id,
            RagAnswer.support_status == RagSupportStatus.INSUFFICIENT_EVIDENCE,
        ),
    )
    passed_cases, total_cases = session.execute(
        select(func.sum(EvaluationRun.passed_cases), func.sum(EvaluationRun.total_cases)).where(
            EvaluationRun.project_id == project_id,
            EvaluationRun.status == EvaluationRunStatus.COMPLETED,
        )
    ).one()
    pass_rate = (
        float(passed_cases) / float(total_cases)
        if passed_cases is not None and total_cases not in (None, 0)
        else None
    )
    average_rag_latency = session.scalar(
        select(func.avg(RagQuestion.latency_ms)).where(
            RagQuestion.project_id == project_id, RagQuestion.latency_ms.is_not(None)
        )
    )
    average_retrieval_latency = session.scalar(
        select(func.avg(EvaluationRun.average_latency_ms)).where(
            EvaluationRun.project_id == project_id,
            EvaluationRun.evaluation_type == EvaluationType.RETRIEVAL,
            EvaluationRun.status == EvaluationRunStatus.COMPLETED,
            EvaluationRun.average_latency_ms.is_not(None),
        )
    )
    extraction_tokens, extraction_records = _extraction_token_sum(session, project_id)
    rag_tokens, rag_records = _token_sum(session, RagQuestion, project_id)
    evaluation_tokens, evaluation_records = _token_sum(session, EvaluationRun, project_id)
    known_tokens = [
        value for value in (extraction_tokens, rag_tokens, evaluation_tokens) if value is not None
    ]
    average_latency = session.scalar(
        select(func.avg(ExtractionRun.latency_ms)).where(
            ExtractionRun.project_id == project_id, ExtractionRun.latency_ms.is_not(None)
        )
    )

    provider_usage: list[ProviderUsage] = []
    for operation, model in (
        ("Extraction", ExtractionRun),
        ("Grounded Q&A", RagQuestion),
        ("Evaluation", EvaluationRun),
    ):
        rows = session.execute(
            select(model.provider, model.model, func.count(model.id))
            .where(model.project_id == project_id)
            .group_by(model.provider, model.model)
            .order_by(func.count(model.id).desc())
        ).all()
        provider_usage.extend(
            ProviderUsage(provider=row[0], model=row[1], operation=operation, requests=int(row[2]))
            for row in rows
        )

    activity_rows = session.execute(
        select(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(12)
    ).all()
    recent_activity = [
        ActivityItem(
            id=event.id,
            event_type=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
            document_id=event.document_id,
            actor=(user.display_name or user.email or user.external_subject) if user else None,
            created_at=event.created_at,
        )
        for event, user in activity_rows
    ]
    return ProjectOverviewResponse(
        metrics=OverviewMetrics(
            documents=documents,
            documents_ready=ready,
            documents_failed=failed,
            extraction_runs=extraction_runs,
            fields_awaiting_review=awaiting,
            verified_fields=verified,
            rag_questions=questions,
            supported_answers=supported,
            insufficient_evidence_answers=insufficient,
            evaluation_pass_rate=pass_rate,
            average_retrieval_latency_ms=(
                round(float(average_retrieval_latency), 2)
                if average_retrieval_latency is not None
                else None
            ),
            average_rag_latency_ms=(
                round(float(average_rag_latency), 2) if average_rag_latency is not None else None
            ),
        ),
        usage=UsageSummary(
            extraction_tokens=extraction_tokens,
            rag_tokens=rag_tokens,
            evaluation_tokens=evaluation_tokens,
            total_tokens=sum(known_tokens) if known_tokens else None,
            average_provider_latency_ms=(
                round(float(average_latency), 2) if average_latency is not None else None
            ),
            records_with_token_usage=extraction_records + rag_records + evaluation_records,
        ),
        provider_usage=provider_usage,
        recent_activity=recent_activity,
    )


def list_document_index(
    session: Session,
    project_id: str,
    *,
    status: DocumentStatus | None,
    mime_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DocumentIndexResponse:
    _require_project(session, project_id)
    filters: list[Any] = [Document.project_id == project_id]
    if status is not None:
        filters.append(Document.status == status)
    if mime_type:
        filters.append(Document.mime_type == mime_type)
    if created_from:
        filters.append(Document.created_at >= created_from)
    if created_to:
        filters.append(Document.created_at <= created_to)
    total = _count(session, select(func.count(Document.id)).where(*filters))
    documents = session.scalars(
        select(Document)
        .where(*filters)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return DocumentIndexResponse(
        items=[DocumentResponse.model_validate(item) for item in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


def list_review_queue(
    session: Session,
    project_id: str,
    *,
    status: ReviewStatus | None,
    document_id: str | None,
    field_name: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> ReviewQueueResponse:
    _require_project(session, project_id)
    filters: list[Any] = [ExtractionRun.project_id == project_id]
    filters.append(
        ExtractedField.review_status == (status if status is not None else ReviewStatus.UNREVIEWED)
    )
    if document_id:
        filters.append(ExtractedField.document_id == document_id)
    if field_name:
        filters.append(ExtractedField.field_name == field_name)
    if created_from:
        filters.append(ExtractedField.created_at >= created_from)
    if created_to:
        filters.append(ExtractedField.created_at <= created_to)
    base = (
        select(ExtractedField, Document, ExtractionRun)
        .join(ExtractionRun, ExtractionRun.id == ExtractedField.extraction_run_id)
        .join(Document, Document.id == ExtractedField.document_id)
        .where(*filters)
    )
    total = _count(
        session,
        select(func.count(ExtractedField.id))
        .join(ExtractionRun, ExtractionRun.id == ExtractedField.extraction_run_id)
        .where(*filters),
    )
    rows = session.execute(
        base.options(selectinload(ExtractedField.evidence))
        .order_by(ExtractedField.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ReviewQueueResponse(
        items=[
            ReviewQueueItem(
                document_id=document.id,
                document_name=document.original_filename,
                extraction_run_id=run.id,
                provider=run.provider,
                model=run.model,
                field=ExtractedFieldResponse.model_validate(field),
            )
            for field, document, run in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def list_audit_index(
    session: Session,
    project_id: str,
    *,
    event_type: str | None,
    actor_user_id: str | None,
    document_id: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> AuditIndexResponse:
    _require_project(session, project_id)
    filters: list[Any] = [AuditEvent.project_id == project_id]
    if event_type:
        filters.append(AuditEvent.event_type == event_type)
    if actor_user_id:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    if document_id:
        filters.append(AuditEvent.document_id == document_id)
    if created_from:
        filters.append(AuditEvent.created_at >= created_from)
    if created_to:
        filters.append(AuditEvent.created_at <= created_to)
    total = _count(session, select(func.count(AuditEvent.id)).where(*filters))
    rows = session.execute(
        select(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(*filters)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditIndexResponse(
        items=[
            AuditItem(
                id=event.id,
                event_type=event.event_type,
                actor=(user.display_name or user.email or user.external_subject) if user else None,
                document_id=event.document_id,
                target_type=event.target_type,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                metadata=event.event_metadata,
                created_at=event.created_at,
            )
            for event, user in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
