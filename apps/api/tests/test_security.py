"""Milestone 6 identity, RBAC, request-hardening, and isolation tests."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from assureai_api.config import Settings
from assureai_api.main import create_app
from assureai_api.models import AuditEvent, Base


def login(client: TestClient, subject: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/development/login",
        json={"subject": subject, "email": f"{subject}@example.test", "display_name": subject},
    )
    assert response.status_code == 200
    return dict(response.json())


def create_project(client: TestClient, name: str) -> str:
    response = client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_unauthenticated_project_access_is_rejected(
    client: TestClient, project_id: str, engine: Engine
) -> None:
    client.post("/api/v1/auth/logout")
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.json()["error"]["request_id"]
    with Session(engine) as session:
        auth_events = list(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.event_type.in_(["auth.login", "auth.logout"]))
                .order_by(AuditEvent.created_at)
            )
        )
    assert [event.event_type for event in auth_events] == ["auth.login", "auth.logout"]
    assert all(event.project_id is None and event.request_id for event in auth_events)


def test_viewer_mutation_and_editor_owner_action_are_rejected(
    client: TestClient, project_id: str
) -> None:
    owner = client.get("/api/v1/auth/me").json()
    add_viewer = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"external_subject": "viewer", "role": "VIEWER"},
    )
    assert add_viewer.status_code == 201
    login(client, "viewer")
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 200
    denied = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("safe.txt", b"safe content", "text/plain")},
    )
    assert denied.status_code == 403

    login(client, str(owner["external_subject"]))
    added = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"external_subject": "editor", "role": "EDITOR"},
    )
    assert added.status_code == 201
    login(client, "editor")
    assert client.get(f"/api/v1/projects/{project_id}/members").status_code == 403
    assert client.get(f"/api/v1/projects/{project_id}/security/config").status_code == 403


def test_cross_project_resources_are_rejected(client: TestClient) -> None:
    login(client, "owner-a")
    project_a = create_project(client, "A")
    login(client, "owner-b")
    project_b = create_project(client, "B")
    upload = client.post(
        f"/api/v1/projects/{project_b}/documents",
        files={"file": ("safe.txt", b"synthetic safe document", "text/plain")},
    )
    assert upload.status_code == 202
    document_b = upload.json()["id"]

    login(client, "owner-a")
    paths = [
        ("get", f"/api/v1/projects/{project_b}/documents/{document_b}", None),
        ("post", f"/api/v1/projects/{project_b}/documents/{document_b}/extractions", None),
        ("post", f"/api/v1/projects/{project_b}/search", {"query": "condition"}),
        ("post", f"/api/v1/projects/{project_b}/questions", {"question": "condition?"}),
        ("post", f"/api/v1/projects/{project_b}/evaluation-runs", {"dataset_id": "none"}),
        ("get", f"/api/v1/projects/{project_b}/security/config", None),
    ]
    for method, path, payload in paths:
        response = (
            getattr(client, method)(path, json=payload)
            if payload
            else getattr(client, method)(path)
        )
        assert response.status_code == 403, (project_a, path, response.text)


def test_secret_values_are_never_returned(client: TestClient, project_id: str) -> None:
    response = client.get(f"/api/v1/projects/{project_id}/security/config")
    assert response.status_code == 200
    assert response.json()["secret_values_exposed"] is False
    assert "session_secret" not in response.text
    assert "api_key" not in response.text


def test_security_headers_and_safe_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/projects/not-a-project")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"]
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_cors_allowlist_is_enforced(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/projects",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options(
        "/api/v1/projects",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_rate_limit_returns_429(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rate.db'}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_path=str(tmp_path / "documents"),
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
        ai_provider="development",
        embedding_provider="development",
    )
    application = create_app(settings, enqueue_document=lambda _id: None)
    Base.metadata.create_all(application.state.session_factory.kw["bind"])
    with TestClient(application) as rate_client:
        login(rate_client, "rate-owner")
        first = rate_client.post("/api/v1/projects", json={"name": "First"})
        second = rate_client.post("/api/v1/projects", json={"name": "Second"})
    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"
