"""Product workspace aggregates, bounded indexes, reports, and RBAC regression tests."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from assureai_api.ai_providers import DevelopmentAIProvider
from assureai_api.extraction_services import process_extraction_run
from assureai_api.models import Document, DocumentStatus
from assureai_api.services import process_document
from assureai_api.storage import LocalDocumentStorage

REPORT = b"""SYNTHETIC INDUSTRIAL EQUIPMENT INSPECTION
Asset ID: P-204
Manufacturer: Northstar Pumps
Model: CW-40
Inspection date: 2026-11-20
Location: Cooling Water Plant
Finding: Drive-end bearing vibration measured 8.4 mm/s RMS.
Recommendations: Inspect bearing alignment and lubrication.
Inspector: Morgan Lee
"""


def ready_document(client: TestClient, project_id: str, engine: Engine, tmp_path: Path) -> str:
    upload = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("pump-inspection.txt", REPORT, "text/plain")},
    )
    assert upload.status_code == 202
    document_id = str(upload.json()["id"])
    with Session(engine) as session:
        process_document(session, LocalDocumentStorage(tmp_path / "documents"), document_id)
    return document_id


def completed_extraction(
    client: TestClient, project_id: str, document_id: str, engine: Engine
) -> str:
    created = client.post(f"/api/v1/projects/{project_id}/documents/{document_id}/extractions")
    assert created.status_code == 202
    run_id = str(created.json()["id"])
    with Session(engine) as session:
        process_extraction_run(session, provider=DevelopmentAIProvider(), run_id=run_id)
    return run_id


def test_zero_data_overview_never_fabricates_usage(client: TestClient, project_id: str) -> None:
    response = client.get(f"/api/v1/projects/{project_id}/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["documents"] == 0
    assert payload["metrics"]["evaluation_pass_rate"] is None
    assert payload["usage"]["total_tokens"] is None
    assert payload["usage"]["average_provider_latency_ms"] is None
    assert payload["provider_usage"] == []


def test_document_index_filters_and_paginates_persisted_rows(
    client: TestClient, project_id: str, engine: Engine
) -> None:
    with Session(engine) as session:
        for index, status in enumerate(
            [DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.READY]
        ):
            session.add(
                Document(
                    project_id=project_id,
                    original_filename=f"report-{index}.txt",
                    storage_key=f"{project_id}/report-{index}.txt",
                    mime_type="text/plain",
                    file_size=10,
                    sha256_hash=f"{index:064d}",
                    status=status,
                    processing_error="Synthetic failure"
                    if status == DocumentStatus.FAILED
                    else None,
                )
            )
        session.commit()
    response = client.get(
        f"/api/v1/projects/{project_id}/document-index",
        params={"status": "READY", "limit": 1, "offset": 1},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["status"] == "READY"


def test_mixed_overview_review_queue_and_report_use_authoritative_records(
    client: TestClient, project_id: str, engine: Engine, tmp_path: Path
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    run_id = completed_extraction(client, project_id, document_id, engine)
    run = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    ).json()
    field = next(item for item in run["fields"] if item["field_name"] == "asset_id")
    reviewed = client.patch(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}/fields/{field['id']}/review",
        json={"decision": "VERIFIED"},
    )
    assert reviewed.status_code == 200

    overview = client.get(f"/api/v1/projects/{project_id}/overview").json()
    assert overview["metrics"]["documents"] == 1
    assert overview["metrics"]["documents_ready"] == 1
    assert overview["metrics"]["extraction_runs"] == 1
    assert overview["metrics"]["verified_fields"] == 1
    assert overview["metrics"]["fields_awaiting_review"] == 11
    assert overview["usage"]["extraction_tokens"] > 0

    queue = client.get(
        f"/api/v1/projects/{project_id}/review-queue",
        params={"status": "VERIFIED", "document_id": document_id},
    ).json()
    assert queue["total"] == 1
    assert queue["items"][0]["field"]["normalized_value"] == "P-204"
    assert queue["items"][0]["field"]["evidence"][0]["page_number"] is None

    report = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}/report")
    assert report.status_code == 200
    assert report.json()["latest_extraction"]["id"] == run_id
    assert report.json()["latest_extraction"]["fields"][0]["evidence"] is not None


def test_audit_index_is_bounded_and_filterable(
    client: TestClient, project_id: str, engine: Engine, tmp_path: Path
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    completed_extraction(client, project_id, document_id, engine)
    response = client.get(
        f"/api/v1/projects/{project_id}/audit-events",
        params={"event_type": "extraction.completed", "limit": 1},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["event_type"] == "extraction.completed"
    assert response.json()["limit"] == 1


def test_product_routes_preserve_viewer_reads_and_cross_project_isolation(
    client: TestClient, project_id: str
) -> None:
    add = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"external_subject": "product-viewer", "role": "VIEWER"},
    )
    assert add.status_code == 201
    other = client.post("/api/v1/projects", json={"name": "Private second project"}).json()["id"]
    upload = client.post(
        f"/api/v1/projects/{other}/documents",
        files={"file": ("private.txt", b"Private evidence", "text/plain")},
    )
    assert upload.status_code == 202
    private_document = upload.json()["id"]
    login = client.post("/api/v1/auth/development/login", json={"subject": "product-viewer"})
    assert login.status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/overview").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/review-queue").status_code == 200
    assert client.get(f"/api/v1/projects/{other}/overview").status_code == 403
    assert client.get(f"/api/v1/projects/{other}/audit-events").status_code == 403
    assert (
        client.get(f"/api/v1/projects/{other}/documents/{private_document}/report").status_code
        == 403
    )
