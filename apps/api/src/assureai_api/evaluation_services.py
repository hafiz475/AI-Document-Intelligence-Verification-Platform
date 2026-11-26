"""Unified evaluation orchestration over the production AI workflows."""

import logging
import time
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from assureai_api.ai_providers import create_ai_provider, provider_identity
from assureai_api.config import Settings
from assureai_api.embedding_providers import create_embedding_provider, embedding_identity
from assureai_api.evaluation_contracts import (
    ExtractionCaseExpected,
    ExtractionCaseInput,
    RagCaseExpected,
    RagCaseInput,
    RetrievalCaseExpected,
    RetrievalCaseInput,
    validate_case_contracts,
)
from assureai_api.evaluation_metrics import (
    EVALUATOR_VERSION,
    aggregate_metrics,
    compare_values,
    extraction_metrics,
    rag_metrics,
    retrieval_metrics,
)
from assureai_api.extraction_services import (
    create_extraction_run,
    get_extraction_run,
    process_extraction_run,
)
from assureai_api.models import (
    Document,
    DocumentChunk,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationCaseResultStatus,
    EvaluationDataset,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationType,
    RagQuestion,
    RagSupportStatus,
    utc_now,
)
from assureai_api.prompts import (
    ensure_inspection_prompt_v1,
    ensure_rag_prompt_v1,
    get_prompt_version,
)
from assureai_api.rag_contracts import RagAnswerOutput, RagCitationReference
from assureai_api.rag_providers import create_rag_provider, rag_provider_identity
from assureai_api.rag_services import (
    CitationValidationError,
    create_rag_question,
    get_rag_question,
    process_rag_question,
    validate_rag_answer,
)
from assureai_api.retrieval_services import semantic_search
from assureai_api.services import NotFoundError, get_project

logger = logging.getLogger(__name__)


class EvaluationConflictError(ValueError):
    pass


class EvaluationUnavailableError(RuntimeError):
    pass


def create_dataset(
    session: Session,
    *,
    project_id: str,
    name: str,
    description: str | None,
    evaluation_type: EvaluationType,
) -> EvaluationDataset:
    get_project(session, project_id)
    dataset = EvaluationDataset(
        project_id=project_id,
        name=name.strip(),
        description=description.strip() if description else None,
        evaluation_type=evaluation_type,
    )
    session.add(dataset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EvaluationConflictError("Dataset name already exists in this project.") from exc
    session.refresh(dataset)
    logger.info(
        "evaluation.dataset_created",
        extra={"project_id": project_id, "evaluation_dataset_id": dataset.id},
    )
    return dataset


def _dataset_query() -> Any:
    return select(EvaluationDataset).options(selectinload(EvaluationDataset.cases))


def get_dataset(session: Session, project_id: str, dataset_id: str) -> EvaluationDataset:
    get_project(session, project_id)
    dataset = cast(
        EvaluationDataset | None,
        session.scalar(
            _dataset_query().where(
                EvaluationDataset.id == dataset_id,
                EvaluationDataset.project_id == project_id,
            )
        ),
    )
    if dataset is None:
        raise NotFoundError("Evaluation dataset not found in this project.")
    return dataset


def list_datasets(session: Session, project_id: str) -> list[EvaluationDataset]:
    get_project(session, project_id)
    return list(
        session.scalars(
            _dataset_query()
            .where(EvaluationDataset.project_id == project_id)
            .order_by(EvaluationDataset.created_at.desc())
        ).unique()
    )


def _validate_case_scope(
    session: Session,
    *,
    project_id: str,
    evaluation_type: EvaluationType,
    input_json: dict[str, Any],
    expected_json: dict[str, Any],
) -> None:
    document_ids: set[str] = set()
    chunk_ids: set[str] = set()
    if evaluation_type == EvaluationType.EXTRACTION:
        document_ids.add(cast(str, input_json["document_id"]))
        evidence = cast(dict[str, list[dict[str, Any]]], expected_json["expected_evidence"])
        for items in evidence.values():
            chunk_ids.update(cast(str, item["chunk_id"]) for item in items)
    elif evaluation_type == EvaluationType.RETRIEVAL:
        if input_json.get("document_id"):
            document_ids.add(cast(str, input_json["document_id"]))
        document_ids.update(cast(list[str], expected_json["expected_document_ids"]))
        chunk_ids.update(cast(list[str], expected_json["expected_chunk_ids"]))
    else:
        if input_json.get("document_id"):
            document_ids.add(cast(str, input_json["document_id"]))
        chunk_ids.update(cast(list[str], expected_json["required_citation_chunk_ids"]))
        chunk_ids.update(cast(list[str], expected_json["forbidden_citation_chunk_ids"]))

    if document_ids:
        count = session.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.project_id == project_id,
                Document.id.in_(document_ids),
            )
        )
        if count != len(document_ids):
            raise EvaluationConflictError("Case document references must belong to the project.")
    if chunk_ids:
        count = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document)
            .where(
                Document.project_id == project_id,
                DocumentChunk.id.in_(chunk_ids),
            )
        )
        if count != len(chunk_ids):
            raise EvaluationConflictError("Case chunk references must belong to the project.")


def create_case(
    session: Session,
    *,
    project_id: str,
    dataset_id: str,
    name: str,
    input_json: dict[str, Any],
    expected_json: dict[str, Any],
    metadata_json: dict[str, Any],
    max_cases: int,
) -> EvaluationCase:
    dataset = get_dataset(session, project_id, dataset_id)
    if len(dataset.cases) >= max_cases:
        raise EvaluationConflictError(f"Datasets are limited to {max_cases} cases.")
    validated_input, validated_expected = validate_case_contracts(
        dataset.evaluation_type, input_json, expected_json
    )
    _validate_case_scope(
        session,
        project_id=project_id,
        evaluation_type=dataset.evaluation_type,
        input_json=validated_input,
        expected_json=validated_expected,
    )
    evaluation_case = EvaluationCase(
        dataset_id=dataset.id,
        name=name.strip(),
        input_json=validated_input,
        expected_json=validated_expected,
        metadata_json=metadata_json,
    )
    session.add(evaluation_case)
    session.commit()
    session.refresh(evaluation_case)
    return evaluation_case


def update_case(
    session: Session,
    *,
    project_id: str,
    dataset_id: str,
    case_id: str,
    name: str,
    input_json: dict[str, Any],
    expected_json: dict[str, Any],
    metadata_json: dict[str, Any],
) -> EvaluationCase:
    dataset = get_dataset(session, project_id, dataset_id)
    evaluation_case = session.scalar(
        select(EvaluationCase).where(
            EvaluationCase.id == case_id,
            EvaluationCase.dataset_id == dataset.id,
        )
    )
    if evaluation_case is None:
        raise NotFoundError("Evaluation case not found in this dataset.")
    validated_input, validated_expected = validate_case_contracts(
        dataset.evaluation_type, input_json, expected_json
    )
    _validate_case_scope(
        session,
        project_id=project_id,
        evaluation_type=dataset.evaluation_type,
        input_json=validated_input,
        expected_json=validated_expected,
    )
    evaluation_case.name = name.strip()
    evaluation_case.input_json = validated_input
    evaluation_case.expected_json = validated_expected
    evaluation_case.metadata_json = metadata_json
    session.commit()
    session.refresh(evaluation_case)
    return evaluation_case


def _run_provider_config(
    session: Session,
    settings: Settings,
    dataset: EvaluationDataset,
    *,
    prompt_version_id: str | None,
    requested_provider: str | None,
    requested_model: str | None,
    requested_embedding_provider: str | None,
    requested_embedding_model: str | None,
) -> tuple[str, str, str | None, str | None, str | None]:
    prompt_id: str | None = None
    if dataset.evaluation_type == EvaluationType.EXTRACTION:
        default_prompt = ensure_inspection_prompt_v1(session)
        prompt_id = prompt_version_id or default_prompt.id
        prompt = get_prompt_version(session, prompt_id)
        if prompt is None or prompt.prompt_template_id != default_prompt.prompt_template_id:
            raise EvaluationConflictError("Selected prompt is not an extraction prompt.")
        provider, model = provider_identity(settings)
        embedding_provider = embedding_model = None
    elif dataset.evaluation_type == EvaluationType.RAG:
        default_prompt = ensure_rag_prompt_v1(session)
        prompt_id = prompt_version_id or default_prompt.id
        prompt = get_prompt_version(session, prompt_id)
        if prompt is None or prompt.prompt_template_id != default_prompt.prompt_template_id:
            raise EvaluationConflictError("Selected prompt is not a RAG prompt.")
        provider, model = rag_provider_identity(settings)
        embedding_provider, embedding_model, _, _ = embedding_identity(settings)
    else:
        provider, model, _, _ = embedding_identity(settings)
        embedding_provider, embedding_model = provider, model
        if prompt_version_id is not None:
            raise EvaluationConflictError("Retrieval evaluations do not use a prompt version.")

    if provider == "disabled" or (
        dataset.evaluation_type in {EvaluationType.RETRIEVAL, EvaluationType.RAG}
        and embedding_provider == "disabled"
    ):
        raise EvaluationUnavailableError("The required provider is disabled.")
    if requested_provider and requested_provider != provider:
        raise EvaluationConflictError("Requested provider is not configured in this deployment.")
    if requested_embedding_provider and requested_embedding_provider != embedding_provider:
        raise EvaluationConflictError(
            "Requested embedding provider is not configured in this deployment."
        )
    if requested_model:
        if settings.ai_provider == "development" and requested_model != model:
            raise EvaluationConflictError("The development provider has one fixed model.")
        model = requested_model
    if requested_embedding_model:
        if (
            settings.embedding_provider == "development"
            and requested_embedding_model != embedding_model
        ):
            raise EvaluationConflictError("The development embedding provider has one fixed model.")
        embedding_model = requested_embedding_model
        if dataset.evaluation_type == EvaluationType.RETRIEVAL:
            model = requested_embedding_model
    return provider, model, embedding_provider, embedding_model, prompt_id


def create_run(
    session: Session,
    *,
    settings: Settings,
    enqueue: Callable[[str], object],
    project_id: str,
    dataset_id: str,
    prompt_version_id: str | None,
    provider: str | None,
    model: str | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    top_k: int,
) -> EvaluationRun:
    dataset = get_dataset(session, project_id, dataset_id)
    if not dataset.cases:
        raise EvaluationConflictError("Evaluation dataset must contain at least one case.")
    if len(dataset.cases) > settings.evaluation_max_cases:
        raise EvaluationConflictError(
            f"Evaluation runs are limited to {settings.evaluation_max_cases} cases."
        )
    resolved = _run_provider_config(
        session,
        settings,
        dataset,
        prompt_version_id=prompt_version_id,
        requested_provider=provider,
        requested_model=model,
        requested_embedding_provider=embedding_provider,
        requested_embedding_model=embedding_model,
    )
    snapshots = [
        {
            "id": item.id,
            "name": item.name,
            "input": item.input_json,
            "expected": item.expected_json,
            "metadata": item.metadata_json,
        }
        for item in sorted(dataset.cases, key=lambda item: (item.created_at, item.id))
    ]
    run = EvaluationRun(
        project_id=project_id,
        dataset_id=dataset.id,
        evaluation_type=dataset.evaluation_type,
        status=EvaluationRunStatus.QUEUED,
        prompt_version_id=resolved[4],
        provider=resolved[0],
        model=resolved[1],
        embedding_provider=resolved[2],
        embedding_model=resolved[3],
        evaluator_version=EVALUATOR_VERSION,
        total_cases=len(snapshots),
        configuration_json={
            "top_k": top_k,
            "workflow_version": f"{dataset.evaluation_type.value.lower()}-v1",
            "embedding_dimensions": settings.embedding_dimensions,
            "case_snapshots": snapshots,
        },
    )
    session.add(run)
    session.commit()
    logger.info(
        "evaluation.run_created",
        extra={"project_id": project_id, "evaluation_run_id": run.id, "dataset_id": dataset.id},
    )
    try:
        enqueue(run.id)
    except Exception as exc:
        run.status = EvaluationRunStatus.FAILED
        run.completed_at = utc_now()
        run.error_message = "Evaluation run could not be queued."
        session.commit()
        raise EvaluationUnavailableError(run.error_message) from exc
    session.refresh(run)
    return run


def _run_query() -> Any:
    return select(EvaluationRun).options(
        selectinload(EvaluationRun.dataset),
        selectinload(EvaluationRun.prompt_version),
        selectinload(EvaluationRun.case_results).selectinload(EvaluationCaseResult.evaluation_case),
    )


def get_run(session: Session, project_id: str, run_id: str) -> EvaluationRun:
    get_project(session, project_id)
    run = cast(
        EvaluationRun | None,
        session.scalar(
            _run_query().where(
                EvaluationRun.id == run_id,
                EvaluationRun.project_id == project_id,
            )
        ),
    )
    if run is None:
        raise NotFoundError("Evaluation run not found in this project.")
    return run


def list_runs(
    session: Session,
    project_id: str,
    *,
    evaluation_type: EvaluationType | None = None,
    dataset_id: str | None = None,
    status: EvaluationRunStatus | None = None,
) -> list[EvaluationRun]:
    get_project(session, project_id)
    query = _run_query().where(EvaluationRun.project_id == project_id)
    if evaluation_type is not None:
        query = query.where(EvaluationRun.evaluation_type == evaluation_type)
    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)
    if status is not None:
        query = query.where(EvaluationRun.status == status)
    return list(session.scalars(query.order_by(EvaluationRun.created_at.desc())).unique())


def _run_settings(settings: Settings, run: EvaluationRun) -> Settings:
    updates: dict[str, Any] = {}
    if settings.ai_provider == "openai":
        updates["openai_model"] = run.model
    if settings.embedding_provider == "openai" and run.embedding_model:
        updates["openai_embedding_model"] = run.embedding_model
    return settings.model_copy(update=updates)


def _evaluate_extraction(
    session: Session,
    *,
    settings: Settings,
    run: EvaluationRun,
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], float, bool, int, int | None, int | None]:
    case_input = ExtractionCaseInput.model_validate(snapshot["input"])
    expected = ExtractionCaseExpected.model_validate(snapshot["expected"])
    product_run = create_extraction_run(
        session,
        settings=settings,
        enqueue=lambda _: None,
        project_id=run.project_id,
        document_id=case_input.document_id,
        prompt_version_id=run.prompt_version_id,
    )
    process_extraction_run(
        session,
        provider=create_ai_provider(settings),
        run_id=product_run.id,
    )
    product_run = get_extraction_run(
        session, run.project_id, case_input.document_id, product_run.id
    )
    actual_fields = {field.field_name: field.raw_value for field in product_run.fields}
    actual_evidence = {
        field.field_name: [
            {
                "chunk_id": evidence.document_chunk_id,
                "page_number": evidence.page_number,
                "quote": evidence.quote,
            }
            for evidence in field.evidence
        ]
        for field in product_run.fields
    }
    result = extraction_metrics(
        expected.expected_fields,
        actual_fields,
        {
            key: [item.model_dump(mode="json") for item in items]
            for key, items in expected.expected_evidence.items()
        },
        actual_evidence,
    )
    actual = {
        "extraction_run_id": product_run.id,
        "fields": actual_fields,
        "evidence": actual_evidence,
    }
    return (
        actual,
        result.metrics,
        result.score,
        result.passed,
        product_run.latency_ms or 0,
        product_run.input_tokens,
        product_run.output_tokens,
    )


def _evaluate_retrieval(
    session: Session,
    *,
    settings: Settings,
    run: EvaluationRun,
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], float, bool, int, None, None]:
    case_input = RetrievalCaseInput.model_validate(snapshot["input"])
    expected = RetrievalCaseExpected.model_validate(snapshot["expected"])
    response = semantic_search(
        session,
        provider=create_embedding_provider(settings),
        project_id=run.project_id,
        document_id=case_input.document_id,
        query=case_input.query,
        top_k=cast(int, run.configuration_json["top_k"]),
    )
    chunk_ids = [item.chunk_id for item in response.results]
    document_ids = [item.document_id for item in response.results]
    result = retrieval_metrics(
        expected.expected_chunk_ids,
        expected.expected_document_ids,
        chunk_ids,
        document_ids,
        expected.maximum_first_relevant_rank,
    )
    actual = {
        "query": case_input.query,
        "retrieved_chunk_ids": chunk_ids,
        "retrieved_document_ids": document_ids,
        "results": [
            {
                "rank": item.rank,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "similarity_score": item.similarity_score,
            }
            for item in response.results
        ],
    }
    return (
        actual,
        result.metrics,
        result.score,
        result.passed,
        response.query_embedding_latency_ms + response.search_latency_ms,
        None,
        None,
    )


def _citation_validity(session: Session, question: RagQuestion) -> float:
    if question.answer is None or not question.answer.citations:
        return 1.0
    valid = 0
    for citation in question.answer.citations:
        output = RagAnswerOutput(
            answer=question.answer.answer_text,
            support_status=RagSupportStatus.SUPPORTED,
            citations=[
                RagCitationReference(
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    page_number=citation.page_number,
                    quote=citation.quote,
                )
            ],
        )
        try:
            validate_rag_answer(session, question=question, output=output)
            valid += 1
        except CitationValidationError:
            pass
    return valid / len(question.answer.citations)


def _evaluate_rag(
    session: Session,
    *,
    settings: Settings,
    run: EvaluationRun,
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], float, bool, int, int | None, int | None]:
    case_input = RagCaseInput.model_validate(snapshot["input"])
    expected = RagCaseExpected.model_validate(snapshot["expected"])
    question = create_rag_question(
        session,
        settings=settings,
        enqueue=lambda _: None,
        project_id=run.project_id,
        document_id=case_input.document_id,
        question_text=case_input.question,
        top_k=cast(int, run.configuration_json["top_k"]),
        prompt_version_id=run.prompt_version_id,
    )
    # Evaluation invokes the queued product workflow synchronously. Expire around
    # that call to preserve its normal separate-worker session boundary when the
    # production session factory retains loaded relationships across commits.
    session.expire(question)
    process_rag_question(
        session,
        embedding_provider=create_embedding_provider(settings),
        answer_provider=create_rag_provider(settings),
        question_id=question.id,
    )
    session.expire(question)
    question = get_rag_question(session, run.project_id, question.id)
    if question.answer is None:
        raise EvaluationUnavailableError("RAG workflow completed without an answer.")
    validity = _citation_validity(session, question)
    citation_ids = [item.chunk_id for item in question.answer.citations]
    result = rag_metrics(
        expected_support_status=expected.support_status.value,
        actual_support_status=question.answer.support_status.value,
        required_citation_chunk_ids=expected.required_citation_chunk_ids,
        forbidden_citation_chunk_ids=expected.forbidden_citation_chunk_ids,
        citation_chunk_ids=citation_ids,
        citation_validity=validity,
        required_phrases=expected.required_phrases,
        forbidden_phrases=expected.forbidden_phrases,
        answer_text=question.answer.answer_text,
    )
    actual = {
        "rag_question_id": question.id,
        "answer": question.answer.answer_text,
        "support_status": question.answer.support_status.value,
        "citations": [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "page_number": item.page_number,
                "quote": item.quote,
            }
            for item in question.answer.citations
        ],
        "retrieved_sources": [
            {
                "rank": item.rank,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "similarity_score": item.similarity_score,
            }
            for item in question.retrieved_chunks
        ],
    }
    return (
        actual,
        result.metrics,
        result.score,
        result.passed,
        question.latency_ms or 0,
        question.input_tokens,
        question.output_tokens,
    )


def _preflight(settings: Settings, run: EvaluationRun) -> Settings:
    resolved = _run_settings(settings, run)
    if run.evaluation_type == EvaluationType.EXTRACTION:
        if provider_identity(resolved) != (run.provider, run.model):
            raise EvaluationUnavailableError("Extraction provider configuration changed.")
        create_ai_provider(resolved)
    elif run.evaluation_type == EvaluationType.RETRIEVAL:
        provider, model, dimensions, _ = embedding_identity(resolved)
        if (
            provider != run.embedding_provider
            or model != run.embedding_model
            or dimensions != run.configuration_json.get("embedding_dimensions")
        ):
            raise EvaluationUnavailableError("Embedding configuration is incompatible.")
        create_embedding_provider(resolved)
    else:
        if rag_provider_identity(resolved) != (run.provider, run.model):
            raise EvaluationUnavailableError("RAG provider configuration changed.")
        provider, model, dimensions, _ = embedding_identity(resolved)
        if (
            provider != run.embedding_provider
            or model != run.embedding_model
            or dimensions != run.configuration_json.get("embedding_dimensions")
        ):
            raise EvaluationUnavailableError("RAG embedding configuration changed.")
        create_embedding_provider(resolved)
        create_rag_provider(resolved)
    return resolved


def process_evaluation_run(
    session: Session,
    *,
    settings: Settings,
    run_id: str,
) -> None:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        logger.warning("evaluation.run_missing", extra={"evaluation_run_id": run_id})
        return
    if run.status == EvaluationRunStatus.COMPLETED:
        return
    run.status = EvaluationRunStatus.PROCESSING
    run.started_at = utc_now()
    run.completed_at = None
    run.error_message = None
    session.commit()
    logger.info(
        "evaluation.run_started",
        extra={"project_id": run.project_id, "evaluation_run_id": run.id},
    )
    try:
        resolved_settings = _preflight(settings, run)
        snapshots = cast(list[dict[str, Any]], run.configuration_json["case_snapshots"])
        for snapshot in snapshots:
            started = time.perf_counter()
            try:
                if run.evaluation_type == EvaluationType.EXTRACTION:
                    values = _evaluate_extraction(
                        session, settings=resolved_settings, run=run, snapshot=snapshot
                    )
                elif run.evaluation_type == EvaluationType.RETRIEVAL:
                    values = _evaluate_retrieval(
                        session, settings=resolved_settings, run=run, snapshot=snapshot
                    )
                else:
                    values = _evaluate_rag(
                        session, settings=resolved_settings, run=run, snapshot=snapshot
                    )
                latency = max(values[4], round((time.perf_counter() - started) * 1000))
                input_tokens, output_tokens = values[5], values[6]
                session.add(
                    EvaluationCaseResult(
                        evaluation_run_id=run.id,
                        evaluation_case_id=cast(str, snapshot["id"]),
                        status=(
                            EvaluationCaseResultStatus.PASSED
                            if values[3]
                            else EvaluationCaseResultStatus.FAILED
                        ),
                        score=values[2],
                        metrics_json=values[1],
                        case_snapshot_json=snapshot,
                        actual_output_json=values[0],
                        latency_ms=latency,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=(
                            input_tokens + output_tokens
                            if input_tokens is not None and output_tokens is not None
                            else None
                        ),
                    )
                )
                session.commit()
                logger.info(
                    "evaluation.case_completed",
                    extra={
                        "project_id": run.project_id,
                        "evaluation_run_id": run.id,
                        "evaluation_case_id": snapshot["id"],
                    },
                )
            except Exception as exc:
                session.rollback()
                session.add(
                    EvaluationCaseResult(
                        evaluation_run_id=run.id,
                        evaluation_case_id=cast(str, snapshot["id"]),
                        status=EvaluationCaseResultStatus.ERROR,
                        score=None,
                        metrics_json={},
                        case_snapshot_json=snapshot,
                        actual_output_json={},
                        error_message=str(exc)[:1000],
                        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
                    )
                )
                session.commit()
                logger.exception(
                    "evaluation.case_failed",
                    extra={
                        "project_id": run.project_id,
                        "evaluation_run_id": run.id,
                        "evaluation_case_id": snapshot["id"],
                    },
                )

        run = session.get(EvaluationRun, run_id)
        if run is None:
            return
        results = list(
            session.scalars(
                select(EvaluationCaseResult).where(EvaluationCaseResult.evaluation_run_id == run.id)
            )
        )
        scored = [item for item in results if item.score is not None]
        latencies = [item.latency_ms for item in results]
        run.passed_cases = sum(item.status == EvaluationCaseResultStatus.PASSED for item in results)
        run.failed_cases = sum(item.status == EvaluationCaseResultStatus.FAILED for item in results)
        run.error_cases = sum(item.status == EvaluationCaseResultStatus.ERROR for item in results)
        run.average_score = (
            sum(cast(float, item.score) for item in scored) / len(scored) if scored else None
        )
        run.average_latency_ms = sum(latencies) / len(latencies) if latencies else None
        run.input_tokens = sum(item.input_tokens or 0 for item in results) or None
        run.output_tokens = sum(item.output_tokens or 0 for item in results) or None
        run.total_tokens = sum(item.total_tokens or 0 for item in results) or None
        run.aggregate_metrics_json = aggregate_metrics(
            [
                item.metrics_json
                for item in results
                if item.status != EvaluationCaseResultStatus.ERROR
            ]
        )
        run.aggregate_metrics_json["pass_rate"] = (
            run.passed_cases / run.total_cases if run.total_cases else 0.0
        )
        run.status = EvaluationRunStatus.COMPLETED
        run.completed_at = utc_now()
        session.commit()
        logger.info(
            "evaluation.run_completed",
            extra={"project_id": run.project_id, "evaluation_run_id": run.id},
        )
    except Exception as exc:
        session.rollback()
        failed = session.get(EvaluationRun, run_id)
        if failed is not None:
            failed.status = EvaluationRunStatus.FAILED
            failed.completed_at = utc_now()
            failed.error_message = str(exc)[:1000]
            session.commit()
            logger.exception(
                "evaluation.run_failed",
                extra={"project_id": failed.project_id, "evaluation_run_id": failed.id},
            )
        raise


def compare_runs(
    session: Session,
    *,
    project_id: str,
    run_a_id: str,
    run_b_id: str,
    thresholds: dict[str, float],
    allow_incompatible_embeddings: bool,
) -> dict[str, Any]:
    run_a = get_run(session, project_id, run_a_id)
    run_b = get_run(session, project_id, run_b_id)
    if (
        run_a.status != EvaluationRunStatus.COMPLETED
        or run_b.status != EvaluationRunStatus.COMPLETED
    ):
        raise EvaluationConflictError("Only completed runs can be compared.")
    if run_a.dataset_id != run_b.dataset_id:
        raise EvaluationConflictError("Comparison runs must use the same dataset.")
    if run_a.configuration_json.get("case_snapshots") != run_b.configuration_json.get(
        "case_snapshots"
    ):
        raise EvaluationConflictError("Comparison runs must use identical case snapshots.")
    embedding_compatible = (
        run_a.embedding_provider == run_b.embedding_provider
        and run_a.embedding_model == run_b.embedding_model
        and run_a.configuration_json.get("embedding_dimensions")
        == run_b.configuration_json.get("embedding_dimensions")
    )
    if (
        run_a.evaluation_type in {EvaluationType.RETRIEVAL, EvaluationType.RAG}
        and not embedding_compatible
        and not allow_incompatible_embeddings
    ):
        raise EvaluationConflictError(
            "Embedding configurations differ; explicit incompatible comparison is required."
        )
    values_a: dict[str, float | int | None] = {
        **cast(dict[str, float], run_a.aggregate_metrics_json),
        "average_score": run_a.average_score,
        "average_latency_ms": run_a.average_latency_ms,
        "total_tokens": run_a.total_tokens,
    }
    values_b: dict[str, float | int | None] = {
        **cast(dict[str, float], run_b.aggregate_metrics_json),
        "average_score": run_b.average_score,
        "average_latency_ms": run_b.average_latency_ms,
        "total_tokens": run_b.total_tokens,
    }
    comparison = compare_values(values_a, values_b, thresholds)
    comparison.update(
        {
            "run_a_id": run_a.id,
            "run_b_id": run_b.id,
            "dataset_id": run_a.dataset_id,
            "embedding_compatible": embedding_compatible,
        }
    )
    return comparison
