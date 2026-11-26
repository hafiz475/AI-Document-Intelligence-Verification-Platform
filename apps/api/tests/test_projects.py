"""Project API behavior."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from assureai_api.models import AuditEvent, Document


def test_create_list_and_get_project(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects",
        json={"name": "Wind Farm Alpha", "description": "North array"},
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Wind Farm Alpha"
    assert project["document_count"] == 0

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project["id"]]

    detail = client.get(f"/api/v1/projects/{project['id']}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "North array"


def test_invalid_project_returns_not_found(client: TestClient) -> None:
    assert client.get("/api/v1/projects/missing").status_code == 404


def test_invalid_project_payload_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "", "description": None})
    assert response.status_code == 422
    whitespace = client.post("/api/v1/projects", json={"name": "   "})
    assert whitespace.status_code == 422


def test_owner_project_deletion_removes_storage_and_preserves_global_audit(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Deletion test"}).json()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("deletion.txt", b"synthetic deletion test", "text/plain")},
    )
    assert upload.status_code == 202
    with Session(engine) as session:
        document = session.scalar(select(Document).where(Document.id == upload.json()["id"]))
        assert document is not None
        storage_path = tmp_path / "documents" / Path(document.storage_key)
    assert storage_path.is_file()

    deleted = client.delete(f"/api/v1/projects/{project['id']}")
    assert deleted.status_code == 204
    assert not storage_path.exists()
    with Session(engine) as session:
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "project.deleted",
                AuditEvent.project_id.is_(None),
                AuditEvent.target_id == project["id"],
            )
        )
    assert audit is not None
    assert audit.actor_user_id is not None
