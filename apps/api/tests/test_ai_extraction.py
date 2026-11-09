"""Milestone 2 structured extraction, evidence, review, and isolation tests."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from assureai_api.ai_contracts import ProviderResult, SourceChunk
from assureai_api.ai_providers import AIProviderError, DevelopmentAIProvider
from assureai_api.extraction_services import process_extraction_run
from assureai_api.models import (
    Document,
    DocumentChunk,
    ExtractedField,
    ExtractionRun,
    PromptVersion,
)
from assureai_api.services import process_document
from assureai_api.storage import LocalDocumentStorage

REPORT = b"""SYNTHETIC DEMO DATA
WIND TURBINE PERIODIC INSPECTION REPORT

Asset ID: WT-204
Manufacturer: Northstar Renewable Systems
Model: NSR-4.2
Inspection date: 2026-10-18
Location: Wind Farm Alpha, Turbine 14

Blade condition
Blade A showed a 35 mm superficial leading-edge coating chip.

Recommendations
1. Repair the Blade A coating chip during the next maintenance window.
2. Continue monthly vibration trending.

Inspector: Morgan Lee
Next inspection date: 2027-04-18
"""


def ready_document(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    *,
    name: str = "inspection.txt",
    content: bytes = REPORT,
) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": (name, content, "text/plain")},
    )
    assert response.status_code == 202
    document_id = str(response.json()["id"])
    with Session(engine) as session:
        process_document(session, LocalDocumentStorage(tmp_path / "documents"), document_id)
    return document_id


def create_run(client: TestClient, project_id: str, document_id: str) -> str:
    response = client.post(f"/api/v1/projects/{project_id}/documents/{document_id}/extractions")
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    return str(response.json()["id"])


class MutatingProvider:
    provider_name = "test"
    model_name = "mutating-test-v1"

    def __init__(self, mutate: Callable[[dict[str, Any], list[SourceChunk]], None]) -> None:
        self.mutate = mutate

    def extract_structured(self, *, prompt: str, chunks: list[SourceChunk]) -> ProviderResult:
        result = DevelopmentAIProvider().extract_structured(prompt=prompt, chunks=chunks)
        self.mutate(result.structured_data, chunks)
        return result.model_copy(update={"provider": self.provider_name, "model": self.model_name})


class FailingProvider:
    provider_name = "test"
    model_name = "failing-test-v1"

    def extract_structured(self, *, prompt: str, chunks: list[SourceChunk]) -> ProviderResult:
        raise AIProviderError("Synthetic provider failure.")


def test_development_provider_lifecycle_missing_fields_and_retry_idempotency(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    queued_extractions: list[str],
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    run_id = create_run(client, project_id, document_id)
    assert queued_extractions == [run_id]

    with Session(engine) as session:
        process_extraction_run(session, provider=DevelopmentAIProvider(), run_id=run_id)
        process_extraction_run(session, provider=DevelopmentAIProvider(), run_id=run_id)

    response = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["provider"] == "development"
    assert payload["model"] == "deterministic-development-v1"
    assert payload["prompt_version"]["version"] == 1
    assert payload["input_tokens"] > 0
    assert payload["output_tokens"] > 0
    fields = {field["field_name"]: field for field in payload["fields"]}
    assert len(fields) == 12
    assert fields["asset_id"]["normalized_value"] == "WT-204"
    assert fields["asset_id"]["support_status"] == "SUPPORTED"
    assert fields["asset_id"]["evidence"][0]["quote"] == "Asset ID: WT-204"
    assert fields["serial_number"]["raw_value"] is None
    assert fields["serial_number"]["missing_reason"] == "not_found"
    assert fields["serial_number"]["support_status"] == "UNSUPPORTED"
    assert {"extraction.created", "extraction.started", "extraction.completed"} <= {
        event["event_type"] for event in payload["audit_events"]
    }

    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ExtractedField)
                .where(ExtractedField.extraction_run_id == run_id)
            )
            == 12
        )
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status.value == "READY"


@pytest.mark.parametrize(
    ("provider", "expected_code"),
    [
        (FailingProvider(), "PROVIDER_ERROR"),
        (MutatingProvider(lambda data, chunks: data.clear()), "STRUCTURED_OUTPUT_INVALID"),
    ],
    ids=["provider-failure", "invalid-structured-response"],
)
def test_failed_extraction_is_safe_and_audited(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    provider: FailingProvider | MutatingProvider,
    expected_code: str,
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    run_id = create_run(client, project_id, document_id)
    with Session(engine) as session, pytest.raises((AIProviderError, RuntimeError)):
        process_extraction_run(session, provider=provider, run_id=run_id)

    payload = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    ).json()
    assert payload["status"] == "FAILED"
    assert payload["error_code"] == expected_code
    assert payload["fields"] == []
    assert payload["audit_events"][-1]["event_type"] == "extraction.failed"


@pytest.mark.parametrize("bad_chunk_id", ["invented-chunk", "cross-document"])
def test_invented_and_cross_document_evidence_is_rejected(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
    bad_chunk_id: str,
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    foreign_document_id = ready_document(
        client,
        project_id,
        engine,
        tmp_path,
        name="other.txt",
        content=b"Asset ID: OTHER-9\nSynthetic unrelated inspection.",
    )
    with Session(engine) as session:
        foreign_chunk_id = session.scalar(
            select(DocumentChunk.id).where(DocumentChunk.document_id == foreign_document_id)
        )
    replacement = str(foreign_chunk_id) if bad_chunk_id == "cross-document" else bad_chunk_id

    def mutate(data: dict[str, Any], chunks: list[SourceChunk]) -> None:
        data["asset_id"]["evidence"][0]["chunk_id"] = replacement

    run_id = create_run(client, project_id, document_id)
    with Session(engine) as session:
        process_extraction_run(session, provider=MutatingProvider(mutate), run_id=run_id)
    payload = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    ).json()
    asset = next(field for field in payload["fields"] if field["field_name"] == "asset_id")
    assert asset["raw_value"] == "WT-204"
    assert asset["support_status"] == "UNSUPPORTED"
    assert asset["evidence"] == []


def test_verify_correct_reject_preserve_originals_and_create_audit_events(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    run_id = create_run(client, project_id, document_id)
    with Session(engine) as session:
        process_extraction_run(session, provider=DevelopmentAIProvider(), run_id=run_id)
    detail_url = f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    fields = {field["field_name"]: field for field in client.get(detail_url).json()["fields"]}

    verify = client.patch(
        f"{detail_url}/fields/{fields['asset_id']['id']}/review",
        json={"decision": "VERIFIED"},
    )
    assert verify.status_code == 200
    assert verify.json()["review_status"] == "VERIFIED"

    correct = client.patch(
        f"{detail_url}/fields/{fields['model']['id']}/review",
        json={
            "decision": "CORRECTED",
            "value": "NSR-4.2-CORRECTED",
            "reason": "Corrected from source evidence.",
        },
    )
    assert correct.status_code == 200
    assert correct.json()["raw_value"] == "NSR-4.2"
    assert correct.json()["normalized_value"] == "NSR-4.2"
    assert correct.json()["corrected_value"] == "NSR-4.2-CORRECTED"

    reject = client.patch(
        f"{detail_url}/fields/{fields['identified_issues']['id']}/review",
        json={"decision": "REJECTED", "reason": "Source does not support this value."},
    )
    assert reject.status_code == 200
    assert reject.json()["review_status"] == "REJECTED"
    assert reject.json()["raw_value"]

    duplicate_review = client.patch(
        f"{detail_url}/fields/{fields['asset_id']['id']}/review",
        json={"decision": "VERIFIED"},
    )
    assert duplicate_review.status_code == 409

    payload = client.get(detail_url).json()
    assert {"field.verified", "field.corrected", "field.rejected"} <= {
        event["event_type"] for event in payload["audit_events"]
    }
    assert all(event["reviewer"] is None for event in payload["audit_events"])


def test_prompt_version_retained_and_project_document_isolation(
    client: TestClient,
    project_id: str,
    engine: Engine,
    tmp_path: Path,
) -> None:
    document_id = ready_document(client, project_id, engine, tmp_path)
    run_id = create_run(client, project_id, document_id)
    with Session(engine) as session:
        original_run = session.get(ExtractionRun, run_id)
        assert original_run is not None
        original_prompt_id = original_run.prompt_version_id
        v1 = session.get(PromptVersion, original_prompt_id)
        assert v1 is not None
        session.add(
            PromptVersion(
                prompt_template_id=v1.prompt_template_id,
                version=2,
                content="A later immutable prompt.",
                schema_version=v1.schema_version,
            )
        )
        session.commit()
        process_extraction_run(session, provider=DevelopmentAIProvider(), run_id=run_id)

    other_project = client.post("/api/v1/projects", json={"name": "Other project"}).json()
    isolated = client.get(
        f"/api/v1/projects/{other_project['id']}/documents/{document_id}/extractions/{run_id}"
    )
    assert isolated.status_code == 404
    payload = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/extractions/{run_id}"
    ).json()
    assert payload["prompt_version"]["id"] == original_prompt_id


def test_extraction_requires_ready_document(client: TestClient, project_id: str) -> None:
    upload = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("waiting.txt", b"Asset ID: WAIT-1", "text/plain")},
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/documents/{upload.json()['id']}/extractions"
    )
    assert response.status_code == 409
