"""Versioned project and document HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from assureai_api.database import get_db
from assureai_api.schemas import (
    ChunkListResponse,
    ChunkResponse,
    DocumentResponse,
    ProjectCreate,
    ProjectResponse,
)
from assureai_api.services import (
    DuplicateDocumentError,
    NotFoundError,
    create_project,
    get_document,
    get_project,
    list_chunks,
    list_documents,
    list_projects,
    upload_document,
)
from assureai_api.storage import DocumentStorage
from assureai_api.uploads import UploadValidationError

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]


def _project_response(project: object, document_count: int) -> ProjectResponse:
    return ProjectResponse.model_validate(project).model_copy(
        update={"document_count": document_count}
    )


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(payload: ProjectCreate, session: DbSession) -> ProjectResponse:
    project = create_project(session, payload.name, payload.description)
    return _project_response(project, 0)


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects_endpoint(session: DbSession) -> list[ProjectResponse]:
    return [_project_response(project, count) for project, count in list_projects(session)]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project_endpoint(project_id: str, session: DbSession) -> ProjectResponse:
    try:
        project, count = get_project(session, project_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return _project_response(project, count)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents_endpoint(project_id: str, session: DbSession) -> list[DocumentResponse]:
    try:
        documents = list_documents(session, project_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return [DocumentResponse.model_validate(document) for document in documents]


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document_endpoint(
    project_id: str,
    request: Request,
    session: DbSession,
    file: Annotated[UploadFile, File(description="PDF, DOCX, or UTF-8 TXT document")],
) -> DocumentResponse:
    content = await file.read(request.app.state.settings.max_upload_bytes + 1)
    storage: DocumentStorage = request.app.state.storage
    try:
        document = upload_document(
            session=session,
            storage=storage,
            enqueue=request.app.state.enqueue_document,
            project_id=project_id,
            filename=file.filename,
            declared_type=file.content_type,
            content=content,
            max_bytes=request.app.state.settings.max_upload_bytes,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "existing_document_id": exc.document_id},
        ) from exc
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The document was saved but processing could not be queued.",
        ) from exc
    return DocumentResponse.model_validate(document)


@router.get(
    "/projects/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_document_endpoint(
    project_id: str, document_id: str, session: DbSession
) -> DocumentResponse:
    try:
        document = get_document(session, project_id, document_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return DocumentResponse.model_validate(document)


@router.get(
    "/projects/{project_id}/documents/{document_id}/chunks",
    response_model=ChunkListResponse,
)
def list_chunks_endpoint(
    project_id: str,
    document_id: str,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChunkListResponse:
    try:
        chunks, total = list_chunks(session, project_id, document_id, limit, offset)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return ChunkListResponse(
        items=[ChunkResponse.model_validate(chunk) for chunk in chunks],
        total=total,
        limit=limit,
        offset=offset,
    )
