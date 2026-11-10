"""Embedding lifecycle, semantic retrieval, and retrieval-only evaluation."""

import hashlib
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from assureai_api.config import Settings
from assureai_api.embedding_contracts import EmbeddingProvider
from assureai_api.embedding_providers import (
    EmbeddingProviderError,
    embedding_identity,
)
from assureai_api.models import (
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
    EmbeddingRun,
    EmbeddingRunStatus,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRun,
    utc_now,
)
from assureai_api.services import NotFoundError, get_document, get_project

logger = logging.getLogger(__name__)


class EmbeddingConflictError(ValueError):
    pass


class EmbeddingUnavailableError(RuntimeError):
    pass


class RetrievalUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    rank: int
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity_score: float
    metadata: dict[str, object]
    embedding_model: str


@dataclass(frozen=True)
class SearchResponseData:
    provider: str
    model: str
    dimensions: int
    query_embedding_latency_ms: int
    search_latency_ms: int
    results: list[SearchResult]


def create_embedding_run(
    session: Session,
    *,
    settings: Settings,
    enqueue: Callable[[str], object],
    project_id: str,
    document_id: str,
) -> EmbeddingRun:
    document = get_document(session, project_id, document_id)
    if document.status != DocumentStatus.READY:
        raise EmbeddingConflictError("Document must be READY before embedding generation.")
    if settings.embedding_provider == "disabled":
        raise EmbeddingUnavailableError("Embedding generation is disabled by configuration.")
    provider, model, dimensions, version = embedding_identity(settings)
    chunks_total = len(document.chunks)
    if chunks_total == 0:
        raise EmbeddingConflictError("Document has no chunks to embed.")
    run = EmbeddingRun(
        project_id=project_id,
        document_id=document_id,
        status=EmbeddingRunStatus.QUEUED,
        provider=provider,
        model=model,
        dimensions=dimensions,
        embedding_version=version,
        chunks_total=chunks_total,
        chunks_embedded=0,
    )
    session.add(run)
    session.commit()
    logger.info(
        "embedding.run_created",
        extra={
            "project_id": project_id,
            "document_id": document_id,
            "embedding_run_id": run.id,
            "provider": provider,
            "model": model,
        },
    )
    try:
        enqueue(run.id)
    except Exception as exc:
        run.status = EmbeddingRunStatus.FAILED
        run.completed_at = utc_now()
        run.error_code = "QUEUE_ERROR"
        run.error_message = "Embedding generation could not be queued."
        session.commit()
        raise EmbeddingUnavailableError(run.error_message) from exc
    session.refresh(run)
    return run


def list_embedding_runs(session: Session, project_id: str, document_id: str) -> list[EmbeddingRun]:
    get_document(session, project_id, document_id)
    return list(
        session.scalars(
            select(EmbeddingRun)
            .where(
                EmbeddingRun.project_id == project_id,
                EmbeddingRun.document_id == document_id,
            )
            .order_by(EmbeddingRun.created_at.desc())
        )
    )


def get_embedding_run(
    session: Session, project_id: str, document_id: str, run_id: str
) -> EmbeddingRun:
    get_document(session, project_id, document_id)
    run = session.scalar(
        select(EmbeddingRun).where(
            EmbeddingRun.id == run_id,
            EmbeddingRun.project_id == project_id,
            EmbeddingRun.document_id == document_id,
        )
    )
    if run is None:
        raise NotFoundError("Embedding run not found in this project and document.")
    return run


def process_embedding_run(
    session: Session,
    *,
    provider: EmbeddingProvider,
    run_id: str,
    batch_size: int,
) -> None:
    run = session.get(EmbeddingRun, run_id)
    if run is None:
        logger.warning("embedding.run_missing", extra={"embedding_run_id": run_id})
        return
    if run.status == EmbeddingRunStatus.COMPLETED:
        return
    run.status = EmbeddingRunStatus.PROCESSING
    run.started_at = utc_now()
    run.completed_at = None
    run.error_code = None
    run.error_message = None
    session.commit()
    logger.info(
        "embedding.started",
        extra={
            "project_id": run.project_id,
            "document_id": run.document_id,
            "embedding_run_id": run.id,
            "provider": run.provider,
            "model": run.model,
        },
    )
    started = time.perf_counter()
    try:
        chunks = list(
            session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == run.document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
        if not chunks:
            raise EmbeddingConflictError("Document has no chunks to embed.")
        if (
            provider.provider_name != run.provider
            or provider.model_name != run.model
            or provider.dimensions != run.dimensions
            or provider.embedding_version != run.embedding_version
        ):
            raise EmbeddingConflictError("Worker embedding configuration does not match the run.")

        vectors: list[list[float]] = []
        input_tokens: int | None = 0
        provider_latency = 0
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset : offset + batch_size]
            result = provider.embed_texts([chunk.content for chunk in batch])
            if (
                result.provider != run.provider
                or result.model != run.model
                or result.dimensions != run.dimensions
                or len(result.vectors) != len(batch)
            ):
                raise EmbeddingProviderError("Provider returned incompatible embeddings.")
            vectors.extend(result.vectors)
            provider_latency += result.latency_ms
            if input_tokens is not None:
                input_tokens = (
                    input_tokens + result.input_tokens if result.input_tokens is not None else None
                )
            logger.info(
                "embedding.batch_completed",
                extra={
                    "project_id": run.project_id,
                    "document_id": run.document_id,
                    "embedding_run_id": run.id,
                    "batch_size": len(batch),
                    "chunks_embedded": len(vectors),
                },
            )

        session.execute(
            delete(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.document_id == run.document_id
            )
        )
        for chunk, vector in zip(chunks, vectors, strict=True):
            session.add(
                DocumentChunkEmbedding(
                    document_chunk_id=chunk.id,
                    project_id=run.project_id,
                    document_id=run.document_id,
                    provider=run.provider,
                    model=run.model,
                    dimensions=run.dimensions,
                    embedding_version=run.embedding_version,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    embedding=vector,
                )
            )
        run.status = EmbeddingRunStatus.COMPLETED
        run.chunks_total = len(chunks)
        run.chunks_embedded = len(vectors)
        run.latency_ms = max(provider_latency, round((time.perf_counter() - started) * 1000))
        run.input_tokens = input_tokens
        run.completed_at = utc_now()
        session.commit()
        logger.info(
            "embedding.completed",
            extra={
                "project_id": run.project_id,
                "document_id": run.document_id,
                "embedding_run_id": run.id,
                "provider": run.provider,
                "model": run.model,
                "latency_ms": run.latency_ms,
            },
        )
    except Exception as exc:
        session.rollback()
        failed = session.get(EmbeddingRun, run_id)
        if failed is not None:
            failed.status = EmbeddingRunStatus.FAILED
            failed.completed_at = utc_now()
            failed.error_code = (
                "PROVIDER_ERROR" if isinstance(exc, EmbeddingProviderError) else "EMBEDDING_ERROR"
            )
            failed.error_message = str(exc) or "Embedding generation failed."
            session.commit()
            logger.exception(
                "embedding.failed",
                extra={
                    "project_id": failed.project_id,
                    "document_id": failed.document_id,
                    "embedding_run_id": failed.id,
                    "provider": failed.provider,
                    "model": failed.model,
                },
            )
        raise


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise RetrievalUnavailableError("Incompatible embedding dimensions.")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_search(
    session: Session,
    *,
    provider: EmbeddingProvider,
    project_id: str,
    query: str,
    top_k: int,
    document_id: str | None = None,
    page_number: int | None = None,
) -> SearchResponseData:
    get_project(session, project_id)
    if document_id is not None:
        get_document(session, project_id, document_id)
    logger.info(
        "retrieval.search_started",
        extra={
            "project_id": project_id,
            "document_id": document_id,
            "provider": provider.provider_name,
            "model": provider.model_name,
            "top_k": top_k,
        },
    )
    started = time.perf_counter()
    try:
        query_result = provider.embed_query(query)
        if len(query_result.vectors) != 1:
            raise RetrievalUnavailableError("Provider returned an invalid query embedding.")
        query_vector = query_result.vectors[0]
        filters = [
            DocumentChunkEmbedding.project_id == project_id,
            DocumentChunkEmbedding.provider == query_result.provider,
            DocumentChunkEmbedding.model == query_result.model,
            DocumentChunkEmbedding.dimensions == query_result.dimensions,
        ]
        if document_id is not None:
            filters.append(DocumentChunkEmbedding.document_id == document_id)
        if page_number is not None:
            filters.append(DocumentChunk.page_number == page_number)

        base = (
            select(DocumentChunkEmbedding, DocumentChunk, Document)
            .join(
                DocumentChunk,
                DocumentChunk.id == DocumentChunkEmbedding.document_chunk_id,
            )
            .join(Document, Document.id == DocumentChunkEmbedding.document_id)
            .where(*filters)
        )
        ranked: list[tuple[DocumentChunkEmbedding, DocumentChunk, Document, float]]
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            distance = DocumentChunkEmbedding.embedding.cosine_distance(query_vector).label(
                "cosine_distance"
            )
            rows = session.execute(base.add_columns(distance).order_by(distance).limit(top_k)).all()
            ranked = [
                (
                    cast(DocumentChunkEmbedding, row[0]),
                    cast(DocumentChunk, row[1]),
                    cast(Document, row[2]),
                    1.0 - cast(float, row[3]),
                )
                for row in rows
            ]
        else:
            candidates = session.execute(base).all()
            ranked = sorted(
                (
                    (
                        embedding,
                        chunk,
                        document,
                        _cosine_similarity(list(embedding.embedding), query_vector),
                    )
                    for embedding, chunk, document in candidates
                ),
                key=lambda item: item[3],
                reverse=True,
            )[:top_k]
        if not ranked:
            raise RetrievalUnavailableError("No compatible embeddings exist for this search scope.")
        search_latency = max(0, round((time.perf_counter() - started) * 1000))
        results = [
            SearchResult(
                rank=index,
                document_id=document.id,
                document_name=document.original_filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                similarity_score=max(-1.0, min(1.0, score)),
                metadata=dict(chunk.chunk_metadata),
                embedding_model=embedding.model,
            )
            for index, (embedding, chunk, document, score) in enumerate(ranked, start=1)
        ]
        logger.info(
            "retrieval.search_completed",
            extra={
                "project_id": project_id,
                "document_id": document_id,
                "provider": query_result.provider,
                "model": query_result.model,
                "top_k": top_k,
                "result_count": len(results),
                "latency_ms": search_latency,
            },
        )
        return SearchResponseData(
            provider=query_result.provider,
            model=query_result.model,
            dimensions=query_result.dimensions,
            query_embedding_latency_ms=query_result.latency_ms,
            search_latency_ms=search_latency,
            results=results,
        )
    except Exception:
        logger.exception(
            "retrieval.search_failed",
            extra={
                "project_id": project_id,
                "document_id": document_id,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "top_k": top_k,
            },
        )
        raise


def calculate_retrieval_metrics(
    expected_chunk_ids: list[str], retrieved_chunk_ids: list[str]
) -> tuple[bool, int | None, float, float]:
    expected = set(expected_chunk_ids)
    if not expected:
        return False, None, 0.0, 0.0
    relevant_positions = [
        index for index, chunk_id in enumerate(retrieved_chunk_ids, start=1) if chunk_id in expected
    ]
    first_rank = min(relevant_positions) if relevant_positions else None
    retrieved_relevant = len(expected.intersection(retrieved_chunk_ids))
    recall = retrieved_relevant / len(expected)
    reciprocal_rank = 1.0 / first_rank if first_rank is not None else 0.0
    return first_rank is not None, first_rank, recall, reciprocal_rank


def run_retrieval_evaluation(
    session: Session,
    *,
    provider: EmbeddingProvider,
    project_id: str,
    top_k: int,
    cases: list[tuple[str, list[str], str | None]],
) -> RetrievalEvaluationRun:
    get_project(session, project_id)
    started = utc_now()
    logger.info(
        "retrieval.evaluation_started",
        extra={
            "project_id": project_id,
            "provider": provider.provider_name,
            "model": provider.model_name,
            "top_k": top_k,
            "case_count": len(cases),
        },
    )
    case_values: list[tuple[str, list[str], list[str], int | None, bool, float, float]] = []
    for query, expected_ids, document_id in cases:
        expected_filters = [
            Document.project_id == project_id,
            DocumentChunk.id.in_(expected_ids),
        ]
        if document_id is not None:
            expected_filters.append(DocumentChunk.document_id == document_id)
        expected_count = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*expected_filters)
        )
        if expected_count != len(set(expected_ids)):
            raise RetrievalUnavailableError(
                "Expected evaluation chunks must belong to the requested project scope."
            )
        response = semantic_search(
            session,
            provider=provider,
            project_id=project_id,
            document_id=document_id,
            query=query,
            top_k=top_k,
        )
        retrieved_ids = [result.chunk_id for result in response.results]
        hit, first_rank, recall, reciprocal_rank = calculate_retrieval_metrics(
            expected_ids, retrieved_ids
        )
        case_values.append(
            (query, expected_ids, retrieved_ids, first_rank, hit, recall, reciprocal_rank)
        )
    count = len(case_values)
    run = RetrievalEvaluationRun(
        project_id=project_id,
        embedding_provider=provider.provider_name,
        embedding_model=provider.model_name,
        top_k=top_k,
        case_count=count,
        hit_rate=sum(1 for value in case_values if value[4]) / count,
        mean_reciprocal_rank=sum(value[6] for value in case_values) / count,
        recall_at_k=sum(value[5] for value in case_values) / count,
        started_at=started,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()
    for query, expected, retrieved, first_rank, hit, recall, reciprocal_rank in case_values:
        session.add(
            RetrievalEvaluationCaseResult(
                run_id=run.id,
                query=query,
                expected_chunk_ids=expected,
                retrieved_chunk_ids=retrieved,
                first_relevant_rank=first_rank,
                hit=hit,
                recall=recall,
                reciprocal_rank=reciprocal_rank,
            )
        )
    session.commit()
    session.refresh(run)
    logger.info(
        "retrieval.evaluation_completed",
        extra={
            "project_id": project_id,
            "provider": provider.provider_name,
            "model": provider.model_name,
            "top_k": top_k,
            "case_count": count,
        },
    )
    return run


def list_retrieval_evaluations(session: Session, project_id: str) -> list[RetrievalEvaluationRun]:
    get_project(session, project_id)
    return list(
        session.scalars(
            select(RetrievalEvaluationRun)
            .options(selectinload(RetrievalEvaluationRun.case_results))
            .where(RetrievalEvaluationRun.project_id == project_id)
            .order_by(RetrievalEvaluationRun.created_at.desc())
        ).unique()
    )
