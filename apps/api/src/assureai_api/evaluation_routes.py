"""Project-scoped HTTP routes for evaluation datasets, runs, and comparisons."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from assureai_api.database import get_db
from assureai_api.evaluation_schemas import (
    EvaluationCaseResponse,
    EvaluationCaseUpsert,
    EvaluationComparisonRequest,
    EvaluationComparisonResponse,
    EvaluationDatasetCreate,
    EvaluationDatasetResponse,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from assureai_api.evaluation_services import (
    EvaluationConflictError,
    EvaluationUnavailableError,
    compare_runs,
    create_case,
    create_dataset,
    create_run,
    get_dataset,
    get_run,
    list_datasets,
    list_runs,
    update_case,
)
from assureai_api.models import EvaluationDataset, EvaluationRunStatus, EvaluationType
from assureai_api.services import NotFoundError

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]


def _dataset_response(dataset: EvaluationDataset) -> EvaluationDatasetResponse:
    return EvaluationDatasetResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        evaluation_type=dataset.evaluation_type,
        case_count=len(dataset.cases),
        cases=[EvaluationCaseResponse.model_validate(item) for item in dataset.cases],
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, EvaluationConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Case schema does not match the dataset type.",
                "errors": exc.errors(),
            },
        ) from exc
    if isinstance(exc, EvaluationUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    raise exc


@router.post(
    "/projects/{project_id}/evaluation-datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset_endpoint(
    project_id: str, payload: EvaluationDatasetCreate, session: DbSession
) -> EvaluationDatasetResponse:
    try:
        return _dataset_response(
            create_dataset(
                session,
                project_id=project_id,
                name=payload.name,
                description=payload.description,
                evaluation_type=payload.evaluation_type,
            )
        )
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get(
    "/projects/{project_id}/evaluation-datasets",
    response_model=list[EvaluationDatasetResponse],
)
def list_datasets_endpoint(project_id: str, session: DbSession) -> list[EvaluationDatasetResponse]:
    try:
        return [_dataset_response(item) for item in list_datasets(session, project_id)]
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get(
    "/projects/{project_id}/evaluation-datasets/{dataset_id}",
    response_model=EvaluationDatasetResponse,
)
def get_dataset_endpoint(
    project_id: str, dataset_id: str, session: DbSession
) -> EvaluationDatasetResponse:
    try:
        return _dataset_response(get_dataset(session, project_id, dataset_id))
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.post(
    "/projects/{project_id}/evaluation-datasets/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_endpoint(
    project_id: str,
    dataset_id: str,
    payload: EvaluationCaseUpsert,
    request: Request,
    session: DbSession,
) -> EvaluationCaseResponse:
    try:
        return EvaluationCaseResponse.model_validate(
            create_case(
                session,
                project_id=project_id,
                dataset_id=dataset_id,
                name=payload.name,
                input_json=payload.input_json,
                expected_json=payload.expected_json,
                metadata_json=payload.metadata_json,
                max_cases=request.app.state.settings.evaluation_max_cases,
            )
        )
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get(
    "/projects/{project_id}/evaluation-datasets/{dataset_id}/cases",
    response_model=list[EvaluationCaseResponse],
)
def list_cases_endpoint(
    project_id: str, dataset_id: str, session: DbSession
) -> list[EvaluationCaseResponse]:
    try:
        dataset = get_dataset(session, project_id, dataset_id)
        return [EvaluationCaseResponse.model_validate(item) for item in dataset.cases]
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.patch(
    "/projects/{project_id}/evaluation-datasets/{dataset_id}/cases/{case_id}",
    response_model=EvaluationCaseResponse,
)
def update_case_endpoint(
    project_id: str,
    dataset_id: str,
    case_id: str,
    payload: EvaluationCaseUpsert,
    session: DbSession,
) -> EvaluationCaseResponse:
    try:
        return EvaluationCaseResponse.model_validate(
            update_case(
                session,
                project_id=project_id,
                dataset_id=dataset_id,
                case_id=case_id,
                name=payload.name,
                input_json=payload.input_json,
                expected_json=payload.expected_json,
                metadata_json=payload.metadata_json,
            )
        )
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.post(
    "/projects/{project_id}/evaluation-runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run_endpoint(
    project_id: str,
    payload: EvaluationRunCreate,
    request: Request,
    session: DbSession,
) -> EvaluationRunResponse:
    try:
        run = create_run(
            session,
            settings=request.app.state.settings,
            enqueue=request.app.state.enqueue_evaluation,
            project_id=project_id,
            dataset_id=payload.dataset_id,
            prompt_version_id=payload.prompt_version_id,
            provider=payload.provider,
            model=payload.model,
            embedding_provider=payload.embedding_provider,
            embedding_model=payload.embedding_model,
            top_k=payload.top_k,
        )
        return EvaluationRunResponse.model_validate(run)
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get(
    "/projects/{project_id}/evaluation-runs",
    response_model=list[EvaluationRunResponse],
)
def list_runs_endpoint(
    project_id: str,
    session: DbSession,
    evaluation_type: Annotated[EvaluationType | None, Query()] = None,
    dataset_id: str | None = None,
    run_status: Annotated[EvaluationRunStatus | None, Query(alias="status")] = None,
    provider_model: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EvaluationRunResponse]:
    try:
        return [
            EvaluationRunResponse.model_validate(item)
            for item in list_runs(
                session,
                project_id,
                evaluation_type=evaluation_type,
                dataset_id=dataset_id,
                status=run_status,
                provider_model=provider_model,
                limit=limit,
                offset=offset,
            )
        ]
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get(
    "/projects/{project_id}/evaluation-runs/{run_id}",
    response_model=EvaluationRunResponse,
)
def get_run_endpoint(project_id: str, run_id: str, session: DbSession) -> EvaluationRunResponse:
    try:
        return EvaluationRunResponse.model_validate(get_run(session, project_id, run_id))
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.post(
    "/projects/{project_id}/evaluation-comparisons",
    response_model=EvaluationComparisonResponse,
)
def compare_runs_endpoint(
    project_id: str,
    payload: EvaluationComparisonRequest,
    session: DbSession,
) -> EvaluationComparisonResponse:
    try:
        thresholds: dict[str, float] = {
            key: value
            for key, value in payload.thresholds.model_dump().items()
            if value is not None
        }
        result: dict[str, Any] = compare_runs(
            session,
            project_id=project_id,
            run_a_id=payload.run_a_id,
            run_b_id=payload.run_b_id,
            thresholds=thresholds,
            allow_incompatible_embeddings=payload.allow_incompatible_embeddings,
        )
        return EvaluationComparisonResponse.model_validate(result)
    except Exception as exc:
        _raise_service_error(exc)
        raise
