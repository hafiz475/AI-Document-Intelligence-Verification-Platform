"""Milestone 3 embedding, retrieval, and evaluation behavior."""

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from assureai_api.embedding_contracts import EmbeddingResult
from assureai_api.embedding_providers import (
    DevelopmentEmbeddingProvider,
    EmbeddingProviderError,
)
from assureai_api.models import (
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
    EmbeddingRun,
    EmbeddingRunStatus,
)
from assureai_api.retrieval_services import (
    RetrievalUnavailableError,
    calculate_retrieval_metrics,
    process_embedding_run,
    semantic_search,
)


class FailingEmbeddingProvider:
    provider_name = "development"
    model_name = "deterministic-development-v1"
    dimensions = 64
    embedding_version = "development-hash-v1"

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingProviderError("Synthetic provider failure.")

    def embed_query(self, query: str) -> EmbeddingResult:
        raise EmbeddingProviderError("Synthetic provider failure.")


def _seed_document(
    engine: Engine,
    project_id: str,
    *,
    filename: str,
    chunks: list[tuple[str, int | None]],
) -> tuple[str, list[str]]:
    document_id = str(uuid.uuid4())
    chunk_ids: list[str] = []
    with Session(engine) as session:
        document = Document(
            id=document_id,
            project_id=project_id,
            original_filename=filename,
            storage_key=f"{project_id}/{document_id}/{filename}",
            mime_type="text/plain",
            file_size=sum(len(content) for content, _ in chunks),
            sha256_hash=hashlib.sha256(f"{project_id}:{filename}".encode()).hexdigest(),
            status=DocumentStatus.READY,
            character_count=sum(len(content) for content, _ in chunks),
        )
        session.add(document)
        for index, (content, page_number) in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=index,
                    page_number=page_number,
                    section="Inspection",
                    content=content,
                    character_count=len(content),
                    chunk_metadata={"synthetic": True},
                )
            )
        session.commit()
    return document_id, chunk_ids


def _complete_embedding(
    client: TestClient,
    engine: Engine,
    project_id: str,
    document_id: str,
    queued_embeddings: list[str],
    *,
    provider: DevelopmentEmbeddingProvider | FailingEmbeddingProvider | None = None,
) -> str:
    response = client.post(f"/api/v1/projects/{project_id}/documents/{document_id}/embeddings")
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    run_id = str(response.json()["id"])
    assert queued_embeddings.pop(0) == run_id
    with Session(engine) as session:
        process_embedding_run(
            session,
            provider=provider or DevelopmentEmbeddingProvider(64),
            run_id=run_id,
            batch_size=2,
        )
    return run_id


def test_development_embeddings_are_deterministic_and_fixed_dimension() -> None:
    provider = DevelopmentEmbeddingProvider(64)
    first = provider.embed_texts(["abnormal gearbox vibration", "blade coating chip"])
    second = provider.embed_texts(["abnormal gearbox vibration", "blade coating chip"])
    assert first.vectors == second.vectors
    assert first.dimensions == 64
    assert all(len(vector) == 64 for vector in first.vectors)
    assert provider.provider_name == "development"


def test_embedding_lifecycle_persistence_and_retry_idempotency(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, chunk_ids = _seed_document(
        engine,
        project_id,
        filename="gearbox.txt",
        chunks=[
            ("Abnormal gearbox vibration was detected during the inspection.", 3),
            ("The tower coating remained intact.", 4),
        ],
    )
    run_id = _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    response = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/embeddings/{run_id}"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["chunks_embedded"] == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(DocumentChunkEmbedding)) == 2
        process_embedding_run(
            session,
            provider=DevelopmentEmbeddingProvider(64),
            run_id=run_id,
            batch_size=2,
        )
        assert session.scalar(select(func.count()).select_from(DocumentChunkEmbedding)) == 2
        assert {
            value.document_chunk_id for value in session.scalars(select(DocumentChunkEmbedding))
        } == set(chunk_ids)


def test_provider_failure_marks_run_failed_without_replacing_active_vectors(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, _ = _seed_document(
        engine,
        project_id,
        filename="failure.txt",
        chunks=[("Gearbox inspection evidence.", 1)],
    )
    _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    response = client.post(f"/api/v1/projects/{project_id}/documents/{document_id}/embeddings")
    failed_run_id = str(response.json()["id"])
    queued_embeddings.clear()
    with Session(engine) as session:
        with pytest.raises(EmbeddingProviderError):
            process_embedding_run(
                session,
                provider=FailingEmbeddingProvider(),
                run_id=failed_run_id,
                batch_size=2,
            )
        failed = session.get(EmbeddingRun, failed_run_id)
        assert failed is not None
        assert failed.status == EmbeddingRunStatus.FAILED
        assert session.scalar(select(func.count()).select_from(DocumentChunkEmbedding)) == 1


def test_reembedding_replaces_stale_model_configuration(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, _ = _seed_document(
        engine,
        project_id,
        filename="versioning.txt",
        chunks=[("Manufacturer: Northstar Renewable Systems", 1)],
    )
    _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    with Session(engine) as session:
        replacement = EmbeddingRun(
            project_id=project_id,
            document_id=document_id,
            status=EmbeddingRunStatus.QUEUED,
            provider="development",
            model="deterministic-development-v1",
            dimensions=32,
            embedding_version="development-hash-v1",
            chunks_total=1,
            chunks_embedded=0,
        )
        session.add(replacement)
        session.commit()
        process_embedding_run(
            session,
            provider=DevelopmentEmbeddingProvider(32),
            run_id=replacement.id,
            batch_size=4,
        )
        active = session.scalar(select(DocumentChunkEmbedding))
        assert active is not None
        assert active.dimensions == 32
        assert len(active.embedding) == 32
        assert session.scalar(select(func.count()).select_from(DocumentChunkEmbedding)) == 1


def test_semantic_search_ranking_scopes_filters_and_score_contract(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, chunk_ids = _seed_document(
        engine,
        project_id,
        filename="inspection.txt",
        chunks=[
            ("Abnormal gearbox vibration was detected at the high-speed shaft.", 3),
            ("The blade had a superficial leading-edge coating chip.", 5),
            ("Next inspection date: 2027-04-18.", 7),
        ],
    )
    _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    response = client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "Was abnormal gearbox vibration detected?", "top_k": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "cosine_similarity"
    assert body["results"][0]["chunk_id"] == chunk_ids[0]
    assert body["results"][0]["rank"] == 1
    assert -1 <= body["results"][0]["similarity_score"] <= 1
    assert len(body["results"]) == 2

    scoped = client.post(
        f"/api/v1/projects/{project_id}/documents/{document_id}/search",
        json={"query": "blade damage", "top_k": 5, "page_number": 5},
    )
    assert scoped.status_code == 200
    assert [result["chunk_id"] for result in scoped.json()["results"]] == [chunk_ids[1]]
    assert all(result["document_id"] == document_id for result in scoped.json()["results"])


def test_missing_incompatible_and_invalid_search_are_controlled(
    client: TestClient,
    engine: Engine,
    project_id: str,
) -> None:
    document_id, _ = _seed_document(
        engine,
        project_id,
        filename="missing.txt",
        chunks=[("No embeddings yet.", 1)],
    )
    missing = client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "gearbox", "top_k": 5},
    )
    assert missing.status_code == 409
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "", "top_k": 5},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "gearbox", "top_k": 21},
        ).status_code
        == 422
    )
    with Session(engine) as session, pytest.raises(RetrievalUnavailableError):
        semantic_search(
            session,
            provider=DevelopmentEmbeddingProvider(32),
            project_id=project_id,
            document_id=document_id,
            query="gearbox",
            top_k=5,
        )


def test_project_and_document_isolation(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    other_project = client.post("/api/v1/projects", json={"name": "Other project"}).json()["id"]
    first_document, _ = _seed_document(
        engine,
        project_id,
        filename="first.txt",
        chunks=[("Gearbox vibration evidence belongs to project A.", 1)],
    )
    other_document, other_chunks = _seed_document(
        engine,
        other_project,
        filename="other.txt",
        chunks=[("Gearbox vibration evidence belongs to project B.", 1)],
    )
    _complete_embedding(client, engine, project_id, first_document, queued_embeddings)
    _complete_embedding(client, engine, other_project, other_document, queued_embeddings)
    response = client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "gearbox vibration", "top_k": 20},
    )
    returned = {result["chunk_id"] for result in response.json()["results"]}
    assert returned.isdisjoint(other_chunks)
    cross_scope = client.post(
        f"/api/v1/projects/{project_id}/documents/{other_document}/search",
        json={"query": "gearbox vibration"},
    )
    assert cross_scope.status_code == 404


def test_query_embedding_provider_failure_is_not_hidden(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, _ = _seed_document(
        engine,
        project_id,
        filename="query-failure.txt",
        chunks=[("Gearbox vibration evidence.", 1)],
    )
    _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    with Session(engine) as session, pytest.raises(EmbeddingProviderError):
        semantic_search(
            session,
            provider=FailingEmbeddingProvider(),
            project_id=project_id,
            document_id=document_id,
            query="gearbox vibration",
            top_k=5,
        )


@pytest.mark.parametrize(
    ("expected", "retrieved", "result"),
    [
        (["a"], ["a", "b"], (True, 1, 1.0, 1.0)),
        (["a"], ["b", "a"], (True, 2, 1.0, 0.5)),
        (["a"], ["b"], (False, None, 0.0, 0.0)),
        (["a", "b"], ["b", "c"], (True, 1, 0.5, 1.0)),
        ([], ["a"], (False, None, 0.0, 0.0)),
    ],
)
def test_retrieval_metrics(
    expected: list[str],
    retrieved: list[str],
    result: tuple[bool, int | None, float, float],
) -> None:
    assert calculate_retrieval_metrics(expected, retrieved) == result


def test_retrieval_evaluation_is_persisted_from_real_results(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_embeddings: list[str],
) -> None:
    document_id, chunk_ids = _seed_document(
        engine,
        project_id,
        filename="evaluation.txt",
        chunks=[
            ("Abnormal gearbox vibration was detected.", 3),
            ("Manufacturer: Northstar Renewable Systems.", 1),
        ],
    )
    _complete_embedding(client, engine, project_id, document_id, queued_embeddings)
    response = client.post(
        f"/api/v1/projects/{project_id}/retrieval-evaluations",
        json={
            "top_k": 2,
            "cases": [
                {
                    "query": "gearbox vibration",
                    "expected_chunk_ids": [chunk_ids[0]],
                    "document_id": document_id,
                },
                {
                    "query": "who manufactured the turbine?",
                    "expected_chunk_ids": [chunk_ids[1]],
                    "document_id": document_id,
                },
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["case_count"] == 2
    assert body["hit_rate"] == 1.0
    assert body["mean_reciprocal_rank"] > 0
    assert body["recall_at_k"] == 1.0
    assert len(body["case_results"]) == 2
    history = client.get(f"/api/v1/projects/{project_id}/retrieval-evaluations").json()
    assert history[0]["id"] == body["id"]
