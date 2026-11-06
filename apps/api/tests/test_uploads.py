"""Upload validation, deduplication, and project isolation."""

from typing import cast

from conftest import synthetic_docx, synthetic_pdf
from fastapi.testclient import TestClient
from httpx import Response


def upload(client: TestClient, project_id: str, name: str, content: bytes, mime: str) -> Response:
    return cast(
        Response,
        client.post(
            f"/api/v1/projects/{project_id}/documents",
            files={"file": (name, content, mime)},
        ),
    )


def test_valid_pdf_docx_and_txt_uploads(
    client: TestClient, project_id: str, queued_documents: list[str]
) -> None:
    samples = [
        ("inspection.pdf", synthetic_pdf(), "application/pdf"),
        (
            "inspection.docx",
            synthetic_docx(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("inspection.txt", b"Synthetic inspection\n\nBlade condition: good", "text/plain"),
    ]
    for name, content, mime in samples:
        response = upload(client, project_id, name, content, mime)
        assert response.status_code == 202
        assert response.json()["status"] == "QUEUED"
        assert "storage_key" not in response.json()
    assert len(queued_documents) == 3


def test_invalid_extension_and_type_are_rejected(client: TestClient, project_id: str) -> None:
    assert (
        upload(client, project_id, "malware.exe", b"MZdata", "application/octet-stream").status_code
        == 422
    )
    assert (
        upload(client, project_id, "fake.pdf", b"plain text", "application/pdf").status_code == 422
    )
    assert (
        upload(client, project_id, "fake.txt", b"plain text", "application/pdf").status_code == 422
    )


def test_empty_and_oversized_files_are_rejected(client: TestClient, project_id: str) -> None:
    assert upload(client, project_id, "empty.txt", b"", "text/plain").status_code == 422
    oversized = b"x" * (1024 * 1024 + 1)
    assert upload(client, project_id, "large.txt", oversized, "text/plain").status_code == 422


def test_duplicate_content_in_same_project_conflicts(client: TestClient, project_id: str) -> None:
    content = b"Asset ID: WT-001"
    first = upload(client, project_id, "first.txt", content, "text/plain")
    duplicate = upload(client, project_id, "renamed.txt", content, "text/plain")
    assert first.status_code == 202
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_document_id"] == first.json()["id"]


def test_document_and_chunks_are_isolated_by_project(client: TestClient, project_id: str) -> None:
    document = upload(client, project_id, "report.txt", b"Synthetic report", "text/plain").json()
    other = client.post("/api/v1/projects", json={"name": "Other project"}).json()
    assert (
        client.get(f"/api/v1/projects/{other['id']}/documents/{document['id']}").status_code == 404
    )
    assert (
        client.get(f"/api/v1/projects/{other['id']}/documents/{document['id']}/chunks").status_code
        == 404
    )


def test_unknown_project_upload_is_rejected(client: TestClient) -> None:
    response = upload(client, "missing", "report.txt", b"Synthetic report", "text/plain")
    assert response.status_code == 404
