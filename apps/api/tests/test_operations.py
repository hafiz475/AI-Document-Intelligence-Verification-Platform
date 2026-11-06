"""Tests for process health and readiness contracts."""

from pathlib import Path

from fastapi.testclient import TestClient

from assureai_api.config import Settings
from assureai_api.main import create_app


def test_health_reports_process_is_alive(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'health.db'}",
        storage_path=str(tmp_path / "documents"),
    )
    with TestClient(create_app(settings, enqueue_document=lambda _document_id: None)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api", "version": "0.1.0"}


def test_ready_reports_initialized_application(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'ready.db'}",
        storage_path=str(tmp_path / "documents"),
    )
    with TestClient(create_app(settings, enqueue_document=lambda _document_id: None)) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "api", "version": "0.1.0"}
