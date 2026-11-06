"""Shared isolated database, storage, and synthetic document fixtures."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from assureai_api.config import Settings
from assureai_api.database import create_database_engine
from assureai_api.main import create_app
from assureai_api.models import Base


def synthetic_pdf(text: str = "Synthetic wind turbine inspection report") -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(data)


def synthetic_docx(text: str = "Synthetic gearbox inspection result") -> bytes:
    document = DocxDocument()
    document.add_heading("Synthetic inspection", level=1)
    document.add_paragraph(text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    value = create_database_engine(database_url)
    Base.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def queued_documents() -> list[str]:
    return []


@pytest.fixture
def client(
    engine: Engine,
    database_url: str,
    tmp_path: Path,
    queued_documents: list[str],
) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_path=str(tmp_path / "documents"),
        max_upload_bytes=1024 * 1024,
    )
    application = create_app(
        settings, enqueue_document=lambda document_id: queued_documents.append(document_id)
    )
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def project_id(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Wind Farm Alpha", "description": "Synthetic test project"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])
