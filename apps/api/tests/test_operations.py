"""Tests for process health and readiness contracts."""

from fastapi.testclient import TestClient

from assureai_api.config import Settings
from assureai_api.main import create_app


def test_health_reports_process_is_alive() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api", "version": "0.1.0"}


def test_ready_reports_initialized_application() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "api", "version": "0.1.0"}
