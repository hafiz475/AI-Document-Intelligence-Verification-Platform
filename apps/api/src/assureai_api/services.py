"""Application services for project intake and document processing."""

import hashlib
import logging
import uuid
from collections.abc import Callable

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from assureai_api.chunking import chunk_segments
from assureai_api.extraction import ExtractionError, extract_text
from assureai_api.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    ExtractionRun,
    Project,
    ProjectMembership,
    ProjectRole,
    RagQuestion,
    utc_now,
)
from assureai_api.security import record_audit
from assureai_api.storage import DocumentStorage
from assureai_api.uploads import validate_upload

logger = logging.getLogger(__name__)


class NotFoundError(LookupError):
    pass


class DuplicateDocumentError(ValueError):
    def __init__(self, document_id: str) -> None:
        super().__init__("This document content already exists in the project.")
        self.document_id = document_id


class DeletionConflictError(ValueError):
    pass


def create_project(
    session: Session,
    name: str,
    description: str | None,
    owner_user_id: str,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> Project:
    project = Project(name=name.strip(), description=description.strip() if description else None)
    session.add(project)
    session.flush()
    session.add(
        ProjectMembership(project_id=project.id, user_id=owner_user_id, role=ProjectRole.OWNER)
    )
    record_audit(
        session,
        project_id=project.id,
        event_type="project.created",
        actor_user_id=owner_user_id,
        request_id=request_id,
        trace_id=trace_id,
        target_type="project",
        target_id=project.id,
    )
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session, user_id: str) -> list[tuple[Project, int, ProjectRole]]:
    statement = (
        select(Project, func.count(Document.id), ProjectMembership.role)
        .outerjoin(Document)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .where(ProjectMembership.user_id == user_id)
        .group_by(Project.id, ProjectMembership.role)
        .order_by(Project.created_at.desc())
    )
    return [(project, count, role) for project, count, role in session.execute(statement).all()]


def get_user_role(session: Session, project_id: str, user_id: str) -> ProjectRole:
    role = session.scalar(
        select(ProjectMembership.role).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
    )
    if role is None:
        raise NotFoundError("Project not found.")
    return role


def get_project(session: Session, project_id: str) -> tuple[Project, int]:
    statement = (
        select(Project, func.count(Document.id))
        .outerjoin(Document)
        .where(Project.id == project_id)
        .group_by(Project.id)
    )
    result = session.execute(statement).one_or_none()
    if result is None:
        raise NotFoundError("Project not found.")
    return result[0], result[1]


def list_documents(session: Session, project_id: str) -> list[Document]:
    get_project(session, project_id)
    return list(
        session.scalars(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
    )


def get_document(session: Session, project_id: str, document_id: str) -> Document:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
        )
    )
    if document is None:
        raise NotFoundError("Document not found in this project.")
    return document


def list_chunks(
    session: Session, project_id: str, document_id: str, limit: int, offset: int
) -> tuple[list[DocumentChunk], int]:
    get_document(session, project_id, document_id)
    condition = DocumentChunk.document_id == document_id
    total = session.scalar(select(func.count()).select_from(DocumentChunk).where(condition)) or 0
    chunks = list(
        session.scalars(
            select(DocumentChunk)
            .where(condition)
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
    )
    return chunks, total


def upload_document(
    session: Session,
    storage: DocumentStorage,
    enqueue: Callable[[str], object],
    project_id: str,
    filename: str | None,
    declared_type: str | None,
    content: bytes,
    max_bytes: int,
) -> Document:
    get_project(session, project_id)
    safe_name, validated = validate_upload(filename, declared_type, content, max_bytes)
    digest = hashlib.sha256(content).hexdigest()
    existing = session.scalar(
        select(Document).where(
            Document.project_id == project_id,
            Document.sha256_hash == digest,
        )
    )
    if existing:
        raise DuplicateDocumentError(existing.id)

    document_id = str(uuid.uuid4())
    storage_key = f"{project_id}/{document_id}{validated.extension}"
    document = Document(
        id=document_id,
        project_id=project_id,
        original_filename=safe_name,
        storage_key=storage_key,
        storage_provider=storage.provider,
        storage_container=storage.container,
        mime_type=validated.mime_type,
        file_size=len(content),
        sha256_hash=digest,
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    try:
        session.flush()
        storage.save(storage_key, content, validated.mime_type)
        document.status = DocumentStatus.QUEUED
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        storage.delete(storage_key)
        existing = session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.sha256_hash == digest,
            )
        )
        raise DuplicateDocumentError(existing.id if existing else "") from exc
    except Exception:
        session.rollback()
        storage.delete(storage_key)
        raise

    logger.info(
        "document.uploaded",
        extra={"project_id": project_id, "document_id": document.id},
    )
    try:
        enqueue(document.id)
        logger.info(
            "document.queued",
            extra={"project_id": project_id, "document_id": document.id},
        )
    except Exception:
        document.status = DocumentStatus.FAILED
        document.processing_error = "Document processing could not be queued."
        document.processed_at = utc_now()
        session.commit()
        logger.exception(
            "document.queue_failed",
            extra={"project_id": project_id, "document_id": document.id},
        )
        raise
    session.refresh(document)
    return document


def delete_document(
    session: Session, storage: DocumentStorage, project_id: str, document_id: str
) -> None:
    document = get_document(session, project_id, document_id)
    has_history = session.scalar(
        select(ExtractionRun.id).where(ExtractionRun.document_id == document_id).limit(1)
    ) or session.scalar(
        select(RagQuestion.id).where(RagQuestion.document_id == document_id).limit(1)
    )
    if has_history:
        raise DeletionConflictError(
            "Document deletion is blocked because immutable extraction or RAG history exists."
        )
    storage.delete(document.storage_key)
    session.delete(document)
    session.commit()


def delete_project(session: Session, storage: DocumentStorage, project_id: str) -> list[str]:
    project, _ = get_project(session, project_id)
    documents = list(session.scalars(select(Document).where(Document.project_id == project_id)))
    document_ids = [document.id for document in documents]
    for document in documents:
        storage.delete(document.storage_key)
    session.delete(project)
    session.commit()
    return document_ids


def process_document(session: Session, storage: DocumentStorage, document_id: str) -> None:
    document = session.get(Document, document_id)
    if document is None:
        logger.warning("document.processing_missing", extra={"document_id": document_id})
        return

    document.status = DocumentStatus.PROCESSING
    document.processing_error = None
    document.processed_at = None
    session.commit()
    logger.info(
        "document.processing_started",
        extra={"project_id": document.project_id, "document_id": document.id},
    )

    try:
        with storage.open(document.storage_key) as stream:
            extracted = extract_text(stream, document.mime_type)
        chunks = chunk_segments(extracted.segments)
        if not chunks:
            raise ExtractionError("No extractable text was found in the document.")

        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        for chunk in chunks:
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    content=chunk.content,
                    character_count=len(chunk.content),
                    chunk_metadata=chunk.metadata,
                )
            )
        document.page_count = extracted.page_count
        document.character_count = extracted.character_count
        document.status = DocumentStatus.READY
        document.processed_at = utc_now()
        session.commit()
        logger.info(
            "document.processing_completed",
            extra={"project_id": document.project_id, "document_id": document.id},
        )
    except Exception as exc:
        session.rollback()
        failed_document = session.get(Document, document_id)
        if failed_document is not None:
            failed_document.status = DocumentStatus.FAILED
            failed_document.processing_error = (
                str(exc) if isinstance(exc, ExtractionError) else "Document processing failed."
            )
            failed_document.processed_at = utc_now()
            session.commit()
            logger.exception(
                "document.processing_failed",
                extra={
                    "project_id": failed_document.project_id,
                    "document_id": failed_document.id,
                },
            )
        raise
