"""Versioned project and document HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from assureai_api.database import get_db
from assureai_api.extraction_services import (
    ExtractionConflictError,
    ExtractionUnavailableError,
    create_extraction_run,
    get_extraction_run,
    list_extraction_runs,
    review_extracted_field,
)
from assureai_api.schemas import (
    ChunkListResponse,
    ChunkResponse,
    DocumentResponse,
    ExtractedFieldResponse,
    ExtractionRunResponse,
    FieldReviewRequest,
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


def _conflict(exc: ExtractionConflictError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


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


@router.post(
    "/projects/{project_id}/documents/{document_id}/extractions",
    response_model=ExtractionRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_extraction_endpoint(
    project_id: str,
    document_id: str,
    request: Request,
    session: DbSession,
) -> ExtractionRunResponse:
    try:
        run = create_extraction_run(
            session,
            settings=request.app.state.settings,
            enqueue=request.app.state.enqueue_extraction,
            project_id=project_id,
            document_id=document_id,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ExtractionConflictError as exc:
        raise _conflict(exc) from exc
    except ExtractionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ExtractionRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/documents/{document_id}/extractions",
    response_model=list[ExtractionRunResponse],
)
def list_extractions_endpoint(
    project_id: str, document_id: str, session: DbSession
) -> list[ExtractionRunResponse]:
    try:
        runs = list_extraction_runs(session, project_id, document_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return [ExtractionRunResponse.model_validate(run) for run in runs]


@router.get(
    "/projects/{project_id}/documents/{document_id}/extractions/{run_id}",
    response_model=ExtractionRunResponse,
)
def get_extraction_endpoint(
    project_id: str, document_id: str, run_id: str, session: DbSession
) -> ExtractionRunResponse:
    try:
        run = get_extraction_run(session, project_id, document_id, run_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return ExtractionRunResponse.model_validate(run)


@router.patch(
    "/projects/{project_id}/documents/{document_id}/extractions/{run_id}/fields/{field_id}/review",
    response_model=ExtractedFieldResponse,
)
def review_field_endpoint(
    project_id: str,
    document_id: str,
    run_id: str,
    field_id: str,
    payload: FieldReviewRequest,
    session: DbSession,
) -> ExtractedFieldResponse:
    try:
        field = review_extracted_field(
            session,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            field_id=field_id,
            decision=payload.decision,
            value=payload.value,
            reason=payload.reason,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ExtractionConflictError as exc:
        raise _conflict(exc) from exc
    return ExtractedFieldResponse.model_validate(field)
