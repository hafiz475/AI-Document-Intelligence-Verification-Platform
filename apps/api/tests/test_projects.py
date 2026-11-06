"""Project API behavior."""

from fastapi.testclient import TestClient


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
