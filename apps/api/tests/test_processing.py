"""Extraction, chunk ordering, failures, transitions, and retry idempotency."""

import io
import zipfile
from pathlib import Path

import pytest
from conftest import synthetic_docx, synthetic_pdf
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from assureai_api.extraction import ExtractionError
from assureai_api.models import Document, DocumentChunk, DocumentStatus
from assureai_api.services import process_document
from assureai_api.storage import LocalDocumentStorage


def corrupted_docx() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<broken")
        archive.writestr("word/document.xml", "<broken")
    return output.getvalue()


def upload(client: TestClient, project_id: str, name: str, content: bytes, mime: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": (name, content, mime)},
    )
    assert response.status_code == 202
    return str(response.json()["id"])


@pytest.mark.parametrize(
    ("name", "content", "mime", "expected"),
    [
        (
            "inspection.pdf",
            synthetic_pdf("Blade condition acceptable"),
            "application/pdf",
            "Blade condition",
        ),
        (
            "inspection.docx",
            synthetic_docx("Gearbox condition acceptable"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Gearbox condition",
        ),
        ("inspection.txt", b"Vibration observation: normal", "text/plain", "Vibration observation"),
    ],
    ids=["pdf", "docx", "txt"],
)
def test_successful_extraction_and_chunks(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    name: str,
    content: bytes,
    mime: str,
    expected: str,
) -> None:
    document_id = upload(client, project_id, name, content, mime)
    with Session(engine) as session:
        process_document(session, LocalDocumentStorage(tmp_path / "documents"), document_id)

    detail = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}").json()
    chunks = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}/chunks").json()[
        "items"
    ]
    assert detail["status"] == "READY"
    assert detail["character_count"] > 0
    assert expected in "\n".join(chunk["content"] for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))


def test_long_text_chunking_is_ordered_and_retry_is_idempotent(
    client: TestClient, project_id: str, engine: Engine, tmp_path: Path
) -> None:
    content = (
        "Paragraph one engineering observation. " * 45 + "\n\n" + "Recommendation two. " * 45
    ).encode()
    document_id = upload(client, project_id, "long.txt", content, "text/plain")
    storage = LocalDocumentStorage(tmp_path / "documents")
    with Session(engine) as session:
        process_document(session, storage, document_id)
        first_count = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        process_document(session, storage, document_id)
        second_count = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        indexes = list(
            session.scalars(
                select(DocumentChunk.chunk_index)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
    assert first_count and first_count > 1
    assert second_count == first_count
    assert indexes == list(range(len(indexes)))


@pytest.mark.parametrize(
    ("name", "content", "mime"),
    [
        ("corrupt.pdf", b"%PDF-not-a-real-document", "application/pdf"),
        (
            "corrupt.docx",
            corrupted_docx(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
    ids=["corrupt-pdf", "corrupt-docx"],
)
def test_processing_failure_sets_safe_failed_state(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    name: str,
    content: bytes,
    mime: str,
) -> None:
    document_id = upload(client, project_id, name, content, mime)
    with Session(engine) as session, pytest.raises(ExtractionError):
        process_document(session, LocalDocumentStorage(tmp_path / "documents"), document_id)
    with Session(engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.FAILED
        assert document.processing_error
        assert "Traceback" not in document.processing_error
