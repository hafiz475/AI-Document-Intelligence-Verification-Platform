"""Milestone 4 grounded answer orchestration and API behavior."""

import hashlib
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from assureai_api.embedding_providers import DevelopmentEmbeddingProvider
from assureai_api.models import (
    AuditEvent,
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
    PromptTemplate,
    PromptVersion,
    QuestionRetrievedChunk,
    RagQuestion,
    RagQuestionStatus,
    RagSupportStatus,
)
from assureai_api.prompts import RAG_PROMPT_TEMPLATE_ID, RAG_PROMPT_VERSION_1_ID
from assureai_api.rag_contracts import (
    RagAnswerOutput,
    RagCitationReference,
    RagContextChunk,
    RagProviderResult,
)
from assureai_api.rag_providers import (
    DevelopmentRagAnswerProvider,
    RagProviderError,
)
from assureai_api.rag_services import (
    CitationValidationError,
    get_rag_question,
    process_rag_question,
    validate_rag_answer,
)
from assureai_api.retrieval_services import SearchResponseData


def seed_document(
    engine: Engine,
    project_id: str,
    *,
    filename: str,
    chunks: list[tuple[str, int | None]],
) -> tuple[str, list[str]]:
    document_id = str(uuid.uuid4())
    chunk_ids: list[str] = []
    embedding_provider = DevelopmentEmbeddingProvider(64)
    vectors = embedding_provider.embed_texts([content for content, _ in chunks]).vectors
    with Session(engine) as session:
        session.add(
            Document(
                id=document_id,
                project_id=project_id,
                original_filename=filename,
                storage_key=f"{project_id}/{document_id}/{filename}",
                mime_type="text/plain",
                file_size=sum(len(content) for content, _ in chunks),
                sha256_hash=hashlib.sha256(f"{project_id}:{filename}".encode()).hexdigest(),
                status=DocumentStatus.READY,
                character_count=sum(len(content) for content, _ in chunks),
            )
        )
        for index, ((content, page_number), vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=index,
                    page_number=page_number,
                    section="Inspection",
                    content=content,
                    character_count=len(content),
                    chunk_metadata={"synthetic": True},
                )
            )
            session.add(
                DocumentChunkEmbedding(
                    document_chunk_id=chunk_id,
                    project_id=project_id,
                    document_id=document_id,
                    provider=embedding_provider.provider_name,
                    model=embedding_provider.model_name,
                    dimensions=embedding_provider.dimensions,
                    embedding_version=embedding_provider.embedding_version,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    embedding=vector,
                )
            )
        session.commit()
    return document_id, chunk_ids


def create_question(
    client: TestClient,
    project_id: str,
    queued_rag_questions: list[str],
    question: str,
    *,
    document_id: str | None = None,
    top_k: int = 5,
) -> str:
    path = (
        f"/api/v1/projects/{project_id}/documents/{document_id}/questions"
        if document_id
        else f"/api/v1/projects/{project_id}/questions"
    )
    response = client.post(path, json={"question": question, "top_k": top_k})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["prompt_version"]["id"] == RAG_PROMPT_VERSION_1_ID
    question_id = str(body["id"])
    assert queued_rag_questions.pop(0) == question_id
    return question_id


def complete_question(
    engine: Engine,
    question_id: str,
    *,
    provider: DevelopmentRagAnswerProvider | None = None,
) -> None:
    with Session(engine) as session:
        process_rag_question(
            session,
            embedding_provider=DevelopmentEmbeddingProvider(64),
            answer_provider=provider or DevelopmentRagAnswerProvider(),
            question_id=question_id,
        )


def get_question(client: TestClient, project_id: str, question_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects/{project_id}/questions/{question_id}")
    assert response.status_code == 200
    return dict(response.json())


def test_supported_answer_persists_citation_provenance_and_prompt(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    document_id, chunk_ids = seed_document(
        engine,
        project_id,
        filename="pump-inspection.txt",
        chunks=[
            (
                "Equipment: Cooling Water Pump P-204\n"
                "Observation:\nDrive-end bearing vibration measured 8.4 mm/s RMS.\n"
                "Expected:\nBelow 4.5 mm/s RMS.",
                3,
            )
        ],
    )
    question_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What abnormal condition was detected?",
        document_id=document_id,
    )
    complete_question(engine, question_id)
    body = get_question(client, project_id, question_id)

    assert body["status"] == "COMPLETED"
    answer = body["answer"]
    assert isinstance(answer, dict)
    assert answer["support_status"] == "SUPPORTED"
    assert "8.4 mm/s RMS" in answer["answer_text"]
    assert answer["confidence"] is None
    assert answer["citations"][0]["chunk_id"] == chunk_ids[0]
    assert answer["citations"][0]["page_number"] == 3
    assert body["prompt_version"]["id"] == RAG_PROMPT_VERSION_1_ID
    assert body["total_tokens"] == body["input_tokens"] + body["output_tokens"]
    assert body["retrieved_sources"][0]["embedding_provider"] == "development"
    assert body["retrieved_sources"][0]["embedding_model"] == ("deterministic-development-v1")
    with Session(engine) as session:
        provenance = session.scalars(
            select(QuestionRetrievedChunk).where(QuestionRetrievedChunk.question_id == question_id)
        ).all()
        assert [(item.rank, item.chunk_id) for item in provenance] == [(1, chunk_ids[0])]


def test_multiple_citations_and_partially_supported_answer(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    seed_document(
        engine,
        project_id,
        filename="inspection.txt",
        chunks=[
            ("Finding: Bearing vibration measured 8.4 mm/s RMS.", 1),
            ("Recommendation: Inspect lubrication before continued service.", 2),
        ],
    )
    multiple_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What vibration and lubrication evidence was reported?",
    )
    complete_question(engine, multiple_id)
    multiple = get_question(client, project_id, multiple_id)
    assert len(multiple["answer"]["citations"]) == 2
    assert multiple["answer"]["support_status"] == "SUPPORTED"

    partial_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What vibration and motor temperature readings were reported?",
    )
    complete_question(engine, partial_id)
    partial = get_question(client, project_id, partial_id)
    assert partial["answer"]["support_status"] == "PARTIALLY_SUPPORTED"
    assert len(partial["answer"]["citations"]) >= 1


def test_insufficient_evidence_is_safe_and_deterministic(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    seed_document(
        engine,
        project_id,
        filename="inspection.txt",
        chunks=[("Observation: Bearing vibration measured 8.4 mm/s RMS.", 1)],
    )
    question_ids = [
        create_question(
            client,
            project_id,
            queued_rag_questions,
            "What was the motor winding temperature?",
        )
        for _ in range(2)
    ]
    for question_id in question_ids:
        complete_question(engine, question_id)
    first = get_question(client, project_id, question_ids[0])
    second = get_question(client, project_id, question_ids[1])
    assert first["answer"]["answer_text"] == second["answer"]["answer_text"]
    assert first["answer"]["support_status"] == second["answer"]["support_status"]
    assert first["answer"]["support_status"] == "INSUFFICIENT_EVIDENCE"
    assert first["answer"]["citations"] == []
    assert first["answer"]["answer_text"] == (
        "The available documents do not provide enough evidence to answer this question."
    )


def test_empty_retrieval_becomes_insufficient_evidence(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What was observed?",
    )
    monkeypatch.setattr(
        "assureai_api.rag_services.semantic_search",
        lambda *args, **kwargs: SearchResponseData(
            provider="development",
            model="deterministic-development-v1",
            dimensions=64,
            query_embedding_latency_ms=0,
            search_latency_ms=0,
            results=[],
        ),
    )
    complete_question(engine, question_id)
    body = get_question(client, project_id, question_id)
    assert body["answer"]["support_status"] == "INSUFFICIENT_EVIDENCE"
    assert body["retrieved_sources"] == []


class FailingRagProvider:
    provider_name = "development"
    model_name = "deterministic-rag-development-v1"

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult:
        raise RagProviderError("Synthetic RAG provider failure.")


class InvalidRagProvider:
    provider_name = "development"
    model_name = "deterministic-rag-development-v1"

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult:
        return RagProviderResult(
            structured_data={"answer": "Unvalidated answer"},
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=1,
        )


@pytest.mark.parametrize(
    ("provider", "message"),
    [
        (FailingRagProvider(), "Synthetic RAG provider failure."),
        (InvalidRagProvider(), "RAG provider returned invalid structured output."),
    ],
)
def test_provider_and_invalid_output_fail_safely(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
    provider: FailingRagProvider | InvalidRagProvider,
    message: str,
) -> None:
    seed_document(
        engine,
        project_id,
        filename=f"{type(provider).__name__}.txt",
        chunks=[("Finding: Abnormal bearing vibration was detected.", 1)],
    )
    question_id = create_question(
        client, project_id, queued_rag_questions, "What vibration was detected?"
    )
    with Session(engine) as session, pytest.raises((RagProviderError, RuntimeError)):
        process_rag_question(
            session,
            embedding_provider=DevelopmentEmbeddingProvider(64),
            answer_provider=provider,
            question_id=question_id,
        )
    body = get_question(client, project_id, question_id)
    assert body["status"] == "FAILED"
    assert body["answer"] is None
    assert body["error_message"] == message


def test_project_isolation_for_retrieval_and_question_access(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    other = client.post("/api/v1/projects", json={"name": "Other project"}).json()["id"]
    own_document, _ = seed_document(
        engine,
        project_id,
        filename="own.txt",
        chunks=[("Finding: Own-project bearing vibration was detected.", 1)],
    )
    seed_document(
        engine,
        other,
        filename="other.txt",
        chunks=[("Finding: Other-project secret vibration was detected.", 2)],
    )
    question_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What vibration was detected?",
        document_id=own_document,
    )
    complete_question(engine, question_id)
    body = get_question(client, project_id, question_id)
    assert {item["document_id"] for item in body["retrieved_sources"]} == {own_document}
    assert client.get(f"/api/v1/projects/{other}/questions/{question_id}").status_code == 404


def test_historical_prompt_version_remains_immutable(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    seed_document(
        engine,
        project_id,
        filename="prompt.txt",
        chunks=[("Finding: Bearing vibration was detected.", 1)],
    )
    question_id = create_question(
        client, project_id, queued_rag_questions, "What vibration was detected?"
    )
    complete_question(engine, question_id)
    with Session(engine) as session:
        template = session.get(PromptTemplate, RAG_PROMPT_TEMPLATE_ID)
        assert template is not None
        session.add(
            PromptVersion(
                prompt_template_id=template.id,
                version=2,
                content="A later immutable prompt.",
                schema_version="rag-answer-v2",
            )
        )
        session.commit()
        question = session.get(RagQuestion, question_id)
        assert question is not None
        assert question.prompt_version_id == RAG_PROMPT_VERSION_1_ID
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.rag_question_id == question_id)
        ).all()
        assert {"rag.question_created", "rag.retrieval_completed", "rag.answer_completed"} <= {
            event.event_type for event in events
        }


def test_question_history_and_validation(
    client: TestClient,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    first = create_question(client, project_id, queued_rag_questions, "First valid question?")
    second = create_question(
        client, project_id, queued_rag_questions, "Second valid question?", top_k=10
    )
    history = client.get(f"/api/v1/projects/{project_id}/questions")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [second, first]
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/questions",
            json={"question": " ", "top_k": 11},
        ).status_code
        == 422
    )
    assert all(item["status"] == RagQuestionStatus.QUEUED for item in history.json())


def test_citation_validation_rejects_untrusted_provenance_and_accepts_whitespace(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    document_id, chunk_ids = seed_document(
        engine,
        project_id,
        filename="citations.txt",
        chunks=[
            ("Finding: Drive-end bearing vibration measured 8.4 mm/s RMS.", 3),
            ("Recommendation: Inspect alignment and lubrication.", 4),
        ],
    )
    other_project = client.post("/api/v1/projects", json={"name": "Citation boundary"}).json()["id"]
    other_document_id, other_chunk_ids = seed_document(
        engine,
        other_project,
        filename="other.txt",
        chunks=[("Finding: Confidential cross-project evidence.", 7)],
    )
    question_id = create_question(
        client,
        project_id,
        queued_rag_questions,
        "What vibration was detected?",
    )
    with Session(engine) as session:
        session.add(
            QuestionRetrievedChunk(
                question_id=question_id,
                chunk_id=chunk_ids[0],
                document_id=document_id,
                rank=1,
                similarity_score=0.91,
                embedding_provider="development",
                embedding_model="deterministic-development-v1",
            )
        )
        session.commit()
        question = get_rag_question(session, project_id, question_id)

        def output(
            citation: RagCitationReference | None,
            status: RagSupportStatus = RagSupportStatus.SUPPORTED,
        ) -> RagAnswerOutput:
            return RagAnswerOutput(
                answer="Grounded answer.",
                support_status=status,
                citations=[citation] if citation else [],
            )

        valid = RagCitationReference(
            chunk_id=chunk_ids[0],
            document_id=document_id,
            page_number=3,
            quote="Drive-end   bearing vibration\nmeasured 8.4 mm/s RMS.",
        )
        validated = validate_rag_answer(session, question=question, output=output(valid))
        assert validated[0][1].rank == 1

        invalid_references = [
            RagCitationReference(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                page_number=3,
                quote="Invented.",
            ),
            RagCitationReference(
                chunk_id=chunk_ids[1],
                document_id=document_id,
                page_number=4,
                quote="Inspect alignment and lubrication.",
            ),
            RagCitationReference(
                chunk_id=other_chunk_ids[0],
                document_id=other_document_id,
                page_number=7,
                quote="Confidential cross-project evidence.",
            ),
            valid.model_copy(update={"document_id": other_document_id}),
            valid.model_copy(update={"page_number": 99}),
            valid.model_copy(update={"quote": "Fabricated vibration value 99 mm/s."}),
        ]
        for invalid in invalid_references:
            with pytest.raises(CitationValidationError):
                validate_rag_answer(session, question=question, output=output(invalid))
        with pytest.raises(CitationValidationError):
            validate_rag_answer(session, question=question, output=output(None))
        insufficient = output(None, status=RagSupportStatus.INSUFFICIENT_EVIDENCE)
        assert validate_rag_answer(session, question=question, output=insufficient) == []
        with pytest.raises(CitationValidationError):
            validate_rag_answer(
                session,
                question=question,
                output=output(valid, RagSupportStatus.INSUFFICIENT_EVIDENCE),
            )


class InventedCitationProvider:
    provider_name = "development"
    model_name = "deterministic-rag-development-v1"

    def generate_answer(
        self,
        *,
        prompt: str,
        question: str,
        context: list[RagContextChunk],
    ) -> RagProviderResult:
        source = context[0]
        return RagProviderResult(
            structured_data={
                "answer": "Invented grounded answer.",
                "support_status": "SUPPORTED",
                "citations": [
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "document_id": source.document_id,
                        "page_number": source.page_number,
                        "quote": "Invented quote.",
                    }
                ],
            },
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=1,
        )


def test_invalid_provider_citation_fails_and_is_audited(
    client: TestClient,
    engine: Engine,
    project_id: str,
    queued_rag_questions: list[str],
) -> None:
    seed_document(
        engine,
        project_id,
        filename="rejected-citation.txt",
        chunks=[("Finding: Bearing vibration measured 8.4 mm/s RMS.", 1)],
    )
    question_id = create_question(
        client, project_id, queued_rag_questions, "What vibration was measured?"
    )
    with Session(engine) as session, pytest.raises(CitationValidationError):
        process_rag_question(
            session,
            embedding_provider=DevelopmentEmbeddingProvider(64),
            answer_provider=InventedCitationProvider(),
            question_id=question_id,
        )
    body = get_question(client, project_id, question_id)
    assert body["status"] == "FAILED"
    assert "unknown chunk" in body["error_message"]
    with Session(engine) as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.rag_question_id == question_id)
        ).all()
        assert "rag.citation_rejected" in {event.event_type for event in events}
