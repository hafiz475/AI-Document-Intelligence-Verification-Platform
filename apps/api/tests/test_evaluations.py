"""M5 dataset, run, provenance, real-path, and isolation tests."""

import hashlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from assureai_api.config import Settings
from assureai_api.database import create_session_factory
from assureai_api.embedding_providers import DevelopmentEmbeddingProvider
from assureai_api.evaluation_services import process_evaluation_run
from assureai_api.models import (
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
)


def seed_document(engine: Engine, project_id: str) -> tuple[str, list[str]]:
    document_id = str(uuid.uuid4())
    chunks = [
        (
            "Asset ID: WT-204\nInspection date: 2026-10-18\n"
            "Drive-end bearing vibration measured 8.4 mm/s RMS. Status: ABNORMAL.",
            3,
        ),
        ("Blade coating remained intact during the synthetic inspection.", 4),
    ]
    provider = DevelopmentEmbeddingProvider(64)
    vectors = provider.embed_texts([item[0] for item in chunks]).vectors
    chunk_ids: list[str] = []
    with Session(engine) as session:
        session.add(
            Document(
                id=document_id,
                project_id=project_id,
                original_filename="synthetic-evaluation.txt",
                storage_key=f"{project_id}/{document_id}/synthetic-evaluation.txt",
                mime_type="text/plain",
                file_size=sum(len(item[0]) for item in chunks),
                sha256_hash=hashlib.sha256(document_id.encode()).hexdigest(),
                status=DocumentStatus.READY,
                page_count=4,
                character_count=sum(len(item[0]) for item in chunks),
            )
        )
        for index, ((content, page), vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=index,
                    page_number=page,
                    section="Inspection",
                    content=content,
                    character_count=len(content),
                    chunk_metadata={"synthetic": True},
                )
            )
            session.add(
                DocumentChunkEmbedding(
                    document_chunk_id=chunk_id,
                    project_id=project_id,
                    document_id=document_id,
                    provider=provider.provider_name,
                    model=provider.model_name,
                    dimensions=provider.dimensions,
                    embedding_version=provider.embedding_version,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    embedding=vector,
                )
            )
        session.commit()
    return document_id, chunk_ids


def create_dataset(client: TestClient, project_id: str, evaluation_type: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/evaluation-datasets",
        json={"name": f"{evaluation_type}-{uuid.uuid4()}", "evaluation_type": evaluation_type},
    )
    assert response.status_code == 201
    return dict(response.json())


def add_case(
    client: TestClient,
    project_id: str,
    dataset_id: str,
    input_json: dict[str, object],
    expected_json: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/evaluation-datasets/{dataset_id}/cases",
        json={
            "name": "Synthetic case",
            "input_json": input_json,
            "expected_json": expected_json,
            "metadata_json": {"source": "synthetic"},
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_dataset_case_typed_validation_and_project_isolation(
    client: TestClient, project_id: str, engine: Engine
) -> None:
    document_id, _ = seed_document(engine, project_id)
    dataset = create_dataset(client, project_id, "EXTRACTION")
    case = add_case(
        client,
        project_id,
        str(dataset["id"]),
        {"document_id": document_id},
        {"expected_fields": {"asset_id": "WT-204"}},
    )
    assert case["metadata_json"] == {"source": "synthetic"}
    detail = client.get(f"/api/v1/projects/{project_id}/evaluation-datasets/{dataset['id']}").json()
    assert detail["case_count"] == 1

    invalid = client.post(
        f"/api/v1/projects/{project_id}/evaluation-datasets/{dataset['id']}/cases",
        json={
            "name": "Wrong schema",
            "input_json": {"query": "not extraction"},
            "expected_json": {"expected_chunk_ids": ["x"]},
        },
    )
    assert invalid.status_code == 422

    other = client.post("/api/v1/projects", json={"name": "Other project"}).json()
    assert (
        client.get(
            f"/api/v1/projects/{other['id']}/evaluation-datasets/{dataset['id']}"
        ).status_code
        == 404
    )


def test_case_update_before_execution(client: TestClient, project_id: str, engine: Engine) -> None:
    document_id, _ = seed_document(engine, project_id)
    dataset = create_dataset(client, project_id, "EXTRACTION")
    case = add_case(
        client,
        project_id,
        str(dataset["id"]),
        {"document_id": document_id},
        {"expected_fields": {"asset_id": "old"}},
    )
    response = client.patch(
        f"/api/v1/projects/{project_id}/evaluation-datasets/{dataset['id']}/cases/{case['id']}",
        json={
            "name": "Updated case",
            "input_json": {"document_id": document_id},
            "expected_json": {"expected_fields": {"asset_id": "WT-204"}},
            "metadata_json": {},
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated case"


def test_extraction_run_uses_real_path_and_persists_provenance(
    client: TestClient,
    project_id: str,
    engine: Engine,
    queued_evaluations: list[str],
) -> None:
    document_id, _ = seed_document(engine, project_id)
    dataset = create_dataset(client, project_id, "EXTRACTION")
    add_case(
        client,
        project_id,
        str(dataset["id"]),
        {"document_id": document_id},
        {"expected_fields": {"asset_id": "WT-204"}},
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/evaluation-runs",
        json={"dataset_id": dataset["id"], "top_k": 5},
    )
    assert response.status_code == 202
    run = response.json()
    assert queued_evaluations == [run["id"]]
    assert run["provider"] == "development"
    assert run["model"] == "deterministic-development-v1"
    assert run["prompt_version_id"]
    assert run["evaluator_version"] == "v1"
    with Session(engine) as session:
        process_evaluation_run(
            session,
            settings=Settings(
                environment="test",
                ai_provider="development",
                embedding_provider="development",
                embedding_dimensions=64,
            ),
            run_id=run["id"],
        )
    completed = client.get(f"/api/v1/projects/{project_id}/evaluation-runs/{run['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["passed_cases"] == 1
    assert completed["aggregate_metrics_json"]["field_accuracy"] == 1
    assert completed["case_results"][0]["actual_output_json"]["extraction_run_id"]
    assert completed["case_results"][0]["case_snapshot_json"]["expected"]


def test_retrieval_and_rag_runs_measure_real_outputs(
    client: TestClient,
    project_id: str,
    engine: Engine,
) -> None:
    document_id, chunk_ids = seed_document(engine, project_id)
    settings = Settings(
        environment="test",
        ai_provider="development",
        embedding_provider="development",
        embedding_dimensions=64,
    )
    retrieval = create_dataset(client, project_id, "RETRIEVAL")
    add_case(
        client,
        project_id,
        str(retrieval["id"]),
        {"query": "abnormal vibration", "document_id": document_id},
        {
            "expected_chunk_ids": [chunk_ids[0]],
            "expected_document_ids": [document_id],
        },
    )
    retrieval_run = client.post(
        f"/api/v1/projects/{project_id}/evaluation-runs",
        json={"dataset_id": retrieval["id"], "top_k": 2},
    ).json()
    with create_session_factory(engine)() as session:
        process_evaluation_run(session, settings=settings, run_id=retrieval_run["id"])
    retrieval_done = client.get(
        f"/api/v1/projects/{project_id}/evaluation-runs/{retrieval_run['id']}"
    ).json()
    assert retrieval_done["aggregate_metrics_json"]["chunk_hit_at_k"] == 1
    assert retrieval_done["aggregate_metrics_json"]["chunk_recall_at_k"] == 1
    assert retrieval_done["aggregate_metrics_json"]["chunk_mrr"] == 1
    assert retrieval_done["embedding_model"] == "deterministic-development-v1"

    rag = create_dataset(client, project_id, "RAG")
    add_case(
        client,
        project_id,
        str(rag["id"]),
        {"question": "What abnormal vibration was measured?", "document_id": document_id},
        {
            "support_status": "SUPPORTED",
            "required_citation_chunk_ids": [chunk_ids[0]],
            "required_phrases": ["8.4 mm/s RMS"],
        },
    )
    rag_run = client.post(
        f"/api/v1/projects/{project_id}/evaluation-runs",
        json={"dataset_id": rag["id"], "top_k": 2},
    ).json()
    with create_session_factory(engine)() as session:
        process_evaluation_run(session, settings=settings, run_id=rag_run["id"])
    rag_done = client.get(f"/api/v1/projects/{project_id}/evaluation-runs/{rag_run['id']}").json()
    assert rag_done["aggregate_metrics_json"]["support_status_correct"] == 1
    assert rag_done["aggregate_metrics_json"]["citation_validity"] == 1
    assert rag_done["case_results"][0]["actual_output_json"]["rag_question_id"]


def test_comparison_persists_historical_snapshot_and_returns_deltas(
    client: TestClient,
    project_id: str,
    engine: Engine,
) -> None:
    document_id, chunk_ids = seed_document(engine, project_id)
    dataset = create_dataset(client, project_id, "RETRIEVAL")
    add_case(
        client,
        project_id,
        str(dataset["id"]),
        {"query": "vibration", "document_id": document_id},
        {"expected_chunk_ids": [chunk_ids[0]]},
    )
    settings = Settings(
        environment="test",
        ai_provider="development",
        embedding_provider="development",
        embedding_dimensions=64,
    )
    run_ids: list[str] = []
    for _ in range(2):
        run = client.post(
            f"/api/v1/projects/{project_id}/evaluation-runs",
            json={"dataset_id": dataset["id"], "top_k": 2},
        ).json()
        run_ids.append(str(run["id"]))
        with Session(engine) as session:
            process_evaluation_run(session, settings=settings, run_id=run["id"])
    comparison = client.post(
        f"/api/v1/projects/{project_id}/evaluation-comparisons",
        json={
            "run_a_id": run_ids[0],
            "run_b_id": run_ids[1],
            "thresholds": {"minimum_chunk_recall_at_k": 0.9},
        },
    )
    assert comparison.status_code == 200
    assert comparison.json()["status"] == "PASS"
    assert comparison.json()["embedding_compatible"]
    quality_metrics = {
        item["metric"]: item["delta"]
        for item in comparison.json()["metrics"]
        if item["metric"] in {"chunk_hit_at_k", "chunk_recall_at_k", "chunk_mrr"}
    }
    assert quality_metrics == {
        "chunk_hit_at_k": 0,
        "chunk_mrr": 0,
        "chunk_recall_at_k": 0,
    }
