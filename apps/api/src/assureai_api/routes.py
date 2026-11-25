"""Versioned project and document HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from assureai_api.database import get_db
from assureai_api.embedding_providers import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    create_embedding_provider,
)
from assureai_api.extraction_services import (
    ExtractionConflictError,
    ExtractionUnavailableError,
    create_extraction_run,
    get_extraction_run,
    list_extraction_runs,
    review_extracted_field,
)
from assureai_api.models import RagQuestion
from assureai_api.rag_services import (
    RagUnavailableError,
    create_rag_question,
    get_rag_question,
    list_rag_questions,
)
from assureai_api.retrieval_services import (
    EmbeddingConflictError,
    EmbeddingUnavailableError,
    RetrievalUnavailableError,
    create_embedding_run,
    get_embedding_run,
    list_embedding_runs,
    list_retrieval_evaluations,
    run_retrieval_evaluation,
    semantic_search,
)
from assureai_api.schemas import (
    ChunkListResponse,
    ChunkResponse,
    DocumentResponse,
    EmbeddingRunResponse,
    ExtractedFieldResponse,
    ExtractionRunResponse,
    FieldReviewRequest,
    ProjectCreate,
    ProjectResponse,
    PromptVersionResponse,
    RagAnswerResponse,
    RagCitationResponse,
    RagQuestionCreate,
    RagQuestionResponse,
    RagRetrievedSourceResponse,
    RetrievalEvaluationRequest,
    RetrievalEvaluationRunResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultResponse,
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


def _rag_question_response(question: RagQuestion) -> RagQuestionResponse:
    sources = [
        RagRetrievedSourceResponse(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            document_name=item.document.original_filename,
            page_number=item.chunk.page_number,
            rank=item.rank,
            similarity_score=item.similarity_score,
            content=item.chunk.content,
            embedding_provider=item.embedding_provider,
            embedding_model=item.embedding_model,
        )
        for item in sorted(question.retrieved_chunks, key=lambda item: item.rank)
    ]
    answer = None
    if question.answer is not None:
        answer = RagAnswerResponse(
            id=question.answer.id,
            answer_text=question.answer.answer_text,
            support_status=question.answer.support_status,
            confidence=question.answer.confidence,
            citations=[
                RagCitationResponse(
                    id=citation.id,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    document_name=citation.document.original_filename,
                    page_number=citation.page_number,
                    quote=citation.quote,
                    rank=citation.rank,
                    similarity_score=citation.similarity_score,
                    created_at=citation.created_at,
                )
                for citation in sorted(question.answer.citations, key=lambda item: item.rank)
            ],
            created_at=question.answer.created_at,
        )
    return RagQuestionResponse(
        id=question.id,
        project_id=question.project_id,
        document_id=question.document_id,
        question=question.question,
        status=question.status,
        retrieval_top_k=question.retrieval_top_k,
        provider=question.provider,
        model=question.model,
        prompt_version=PromptVersionResponse.model_validate(question.prompt_version),
        started_at=question.started_at,
        completed_at=question.completed_at,
        latency_ms=question.latency_ms,
        input_tokens=question.input_tokens,
        output_tokens=question.output_tokens,
        total_tokens=question.total_tokens,
        error_message=question.error_message,
        answer=answer,
        retrieved_sources=sources,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


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


@router.post(
    "/projects/{project_id}/documents/{document_id}/embeddings",
    response_model=EmbeddingRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_embeddings_endpoint(
    project_id: str,
    document_id: str,
    request: Request,
    session: DbSession,
) -> EmbeddingRunResponse:
    try:
        run = create_embedding_run(
            session,
            settings=request.app.state.settings,
            enqueue=request.app.state.enqueue_embedding,
            project_id=project_id,
            document_id=document_id,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except EmbeddingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return EmbeddingRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/documents/{document_id}/embeddings",
    response_model=list[EmbeddingRunResponse],
)
def list_embeddings_endpoint(
    project_id: str, document_id: str, session: DbSession
) -> list[EmbeddingRunResponse]:
    try:
        runs = list_embedding_runs(session, project_id, document_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return [EmbeddingRunResponse.model_validate(run) for run in runs]


@router.get(
    "/projects/{project_id}/documents/{document_id}/embeddings/{run_id}",
    response_model=EmbeddingRunResponse,
)
def get_embedding_endpoint(
    project_id: str, document_id: str, run_id: str, session: DbSession
) -> EmbeddingRunResponse:
    try:
        run = get_embedding_run(session, project_id, document_id, run_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return EmbeddingRunResponse.model_validate(run)


def _search(
    *,
    project_id: str,
    payload: SemanticSearchRequest,
    request: Request,
    session: Session,
    document_id: str | None,
) -> SemanticSearchResponse:
    if (
        payload.document_id is not None
        and document_id is not None
        and payload.document_id != document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conflicting document scopes.",
        )
    scope = document_id or payload.document_id
    try:
        provider = create_embedding_provider(request.app.state.settings)
        result = semantic_search(
            session,
            provider=provider,
            project_id=project_id,
            document_id=scope,
            query=payload.query,
            top_k=payload.top_k,
            page_number=payload.page_number,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except RetrievalUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return SemanticSearchResponse(
        query=payload.query,
        provider=result.provider,
        model=result.model,
        dimensions=result.dimensions,
        query_embedding_latency_ms=result.query_embedding_latency_ms,
        search_latency_ms=result.search_latency_ms,
        results=[
            SemanticSearchResultResponse.model_validate(item, from_attributes=True)
            for item in result.results
        ],
    )


@router.post("/projects/{project_id}/search", response_model=SemanticSearchResponse)
def project_search_endpoint(
    project_id: str,
    payload: SemanticSearchRequest,
    request: Request,
    session: DbSession,
) -> SemanticSearchResponse:
    return _search(
        project_id=project_id,
        payload=payload,
        request=request,
        session=session,
        document_id=None,
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/search",
    response_model=SemanticSearchResponse,
)
def document_search_endpoint(
    project_id: str,
    document_id: str,
    payload: SemanticSearchRequest,
    request: Request,
    session: DbSession,
) -> SemanticSearchResponse:
    return _search(
        project_id=project_id,
        payload=payload,
        request=request,
        session=session,
        document_id=document_id,
    )


@router.post(
    "/projects/{project_id}/retrieval-evaluations",
    response_model=RetrievalEvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_retrieval_evaluation_endpoint(
    project_id: str,
    payload: RetrievalEvaluationRequest,
    request: Request,
    session: DbSession,
) -> RetrievalEvaluationRunResponse:
    try:
        provider = create_embedding_provider(request.app.state.settings)
        run = run_retrieval_evaluation(
            session,
            provider=provider,
            project_id=project_id,
            top_k=payload.top_k,
            cases=[
                (item.query, item.expected_chunk_ids, item.document_id) for item in payload.cases
            ],
        )
        run = list_retrieval_evaluations(session, project_id)[0]
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except RetrievalUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return RetrievalEvaluationRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/retrieval-evaluations",
    response_model=list[RetrievalEvaluationRunResponse],
)
def list_retrieval_evaluation_endpoint(
    project_id: str, session: DbSession
) -> list[RetrievalEvaluationRunResponse]:
    try:
        runs = list_retrieval_evaluations(session, project_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return [RetrievalEvaluationRunResponse.model_validate(run) for run in runs]


def _create_question(
    *,
    project_id: str,
    document_id: str | None,
    payload: RagQuestionCreate,
    request: Request,
    session: Session,
) -> RagQuestionResponse:
    try:
        question = create_rag_question(
            session,
            settings=request.app.state.settings,
            enqueue=request.app.state.enqueue_rag_question,
            project_id=project_id,
            document_id=document_id,
            question_text=payload.question,
            top_k=payload.top_k,
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except RagUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return _rag_question_response(question)


@router.post(
    "/projects/{project_id}/questions",
    response_model=RagQuestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_project_question_endpoint(
    project_id: str,
    payload: RagQuestionCreate,
    request: Request,
    session: DbSession,
) -> RagQuestionResponse:
    return _create_question(
        project_id=project_id,
        document_id=None,
        payload=payload,
        request=request,
        session=session,
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/questions",
    response_model=RagQuestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_document_question_endpoint(
    project_id: str,
    document_id: str,
    payload: RagQuestionCreate,
    request: Request,
    session: DbSession,
) -> RagQuestionResponse:
    return _create_question(
        project_id=project_id,
        document_id=document_id,
        payload=payload,
        request=request,
        session=session,
    )


@router.get("/projects/{project_id}/questions", response_model=list[RagQuestionResponse])
def list_questions_endpoint(
    project_id: str,
    session: DbSession,
    document_id: str | None = None,
) -> list[RagQuestionResponse]:
    try:
        questions = list_rag_questions(session, project_id, document_id=document_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return [_rag_question_response(question) for question in questions]


@router.get(
    "/projects/{project_id}/questions/{question_id}",
    response_model=RagQuestionResponse,
)
def get_question_endpoint(
    project_id: str, question_id: str, session: DbSession
) -> RagQuestionResponse:
    try:
        question = get_rag_question(session, project_id, question_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return _rag_question_response(question)
