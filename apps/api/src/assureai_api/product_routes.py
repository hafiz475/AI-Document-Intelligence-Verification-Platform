"""Product-facing aggregate, queue, report, and bounded index endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from assureai_api.database import get_db
from assureai_api.models import (
    Document,
    DocumentStatus,
    ExtractedField,
    ExtractionRun,
    RagAnswer,
    RagQuestion,
    RagSupportStatus,
    ReviewStatus,
)
from assureai_api.product_schemas import (
    AuditIndexResponse,
    DocumentIndexResponse,
    DocumentReportResponse,
    ProjectOverviewResponse,
    ReviewQueueResponse,
)
from assureai_api.product_services import (
    get_project_overview,
    list_audit_index,
    list_document_index,
    list_review_queue,
)
from assureai_api.schemas import DocumentResponse, ExtractionRunResponse
from assureai_api.services import NotFoundError

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/projects/{project_id}/overview", response_model=ProjectOverviewResponse)
def project_overview(project_id: str, session: DbSession) -> ProjectOverviewResponse:
    try:
        return get_project_overview(session, project_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/projects/{project_id}/document-index", response_model=DocumentIndexResponse)
def document_index(
    project_id: str,
    session: DbSession,
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    mime_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentIndexResponse:
    try:
        return list_document_index(
            session,
            project_id,
            status=document_status,
            mime_type=mime_type,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/projects/{project_id}/review-queue", response_model=ReviewQueueResponse)
def review_queue(
    project_id: str,
    session: DbSession,
    review_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    document_id: str | None = None,
    field_name: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewQueueResponse:
    try:
        return list_review_queue(
            session,
            project_id,
            status=review_status,
            document_id=document_id,
            field_name=field_name,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/projects/{project_id}/audit-events", response_model=AuditIndexResponse)
def audit_index(
    project_id: str,
    session: DbSession,
    event_type: str | None = None,
    actor_user_id: str | None = None,
    document_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditIndexResponse:
    try:
        return list_audit_index(
            session,
            project_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            document_id=document_id,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get(
    "/projects/{project_id}/documents/{document_id}/report",
    response_model=DocumentReportResponse,
)
def document_report(
    project_id: str, document_id: str, session: DbSession
) -> DocumentReportResponse:
    document = session.scalar(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    extraction = session.scalars(
        select(ExtractionRun)
        .options(
            selectinload(ExtractionRun.prompt_version),
            selectinload(ExtractionRun.fields).selectinload(ExtractedField.evidence),
            selectinload(ExtractionRun.audit_events),
        )
        .where(ExtractionRun.project_id == project_id, ExtractionRun.document_id == document_id)
        .order_by(ExtractionRun.created_at.desc())
        .limit(1)
    ).first()
    question_count = int(
        session.scalar(
            select(func.count(RagQuestion.id)).where(
                RagQuestion.project_id == project_id, RagQuestion.document_id == document_id
            )
        )
        or 0
    )
    supported = int(
        session.scalar(
            select(func.count(RagAnswer.id))
            .join(RagQuestion, RagQuestion.id == RagAnswer.question_id)
            .where(
                RagQuestion.project_id == project_id,
                RagQuestion.document_id == document_id,
                RagAnswer.support_status == RagSupportStatus.SUPPORTED,
            )
        )
        or 0
    )
    insufficient = int(
        session.scalar(
            select(func.count(RagAnswer.id))
            .join(RagQuestion, RagQuestion.id == RagAnswer.question_id)
            .where(
                RagQuestion.project_id == project_id,
                RagQuestion.document_id == document_id,
                RagAnswer.support_status == RagSupportStatus.INSUFFICIENT_EVIDENCE,
            )
        )
        or 0
    )
    return DocumentReportResponse(
        document=DocumentResponse.model_validate(document),
        latest_extraction=(
            ExtractionRunResponse.model_validate(extraction) if extraction is not None else None
        ),
        question_count=question_count,
        supported_answer_count=supported,
        insufficient_answer_count=insufficient,
    )
