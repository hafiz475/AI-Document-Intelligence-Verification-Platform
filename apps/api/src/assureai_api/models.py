"""Persistence models for document intelligence, retrieval, and grounded answers."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class ExtractionRunStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmbeddingRunStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    VERIFIED = "VERIFIED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"


class SupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class RagQuestionStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RagSupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvaluationType(StrEnum):
    EXTRACTION = "EXTRACTION"
    RETRIEVAL = "RETRIEVAL"
    RAG = "RAG"


class EvaluationRunStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvaluationCaseResultStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"


class ProjectRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("external_subject", name="uq_users_external_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    memberships: Mapped[list["ProjectMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
        Index("ix_project_memberships_user_project", "user_id", "project_id"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[ProjectRole] = mapped_column(
        Enum(ProjectRole, name="project_role", native_enum=False), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    project: Mapped["Project"] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    embedding_runs: Mapped[list["EmbeddingRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    retrieval_evaluation_runs: Mapped[list["RetrievalEvaluationRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    rag_questions: Mapped[list["RagQuestion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    evaluation_datasets: Mapped[list["EvaluationDataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_evaluation_dataset_project_name"),
        Index("ix_evaluation_datasets_project_type", "project_id", "evaluation_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_type: Mapped[EvaluationType] = mapped_column(
        Enum(EvaluationType, name="evaluation_type", native_enum=False)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    project: Mapped[Project] = relationship(back_populates="evaluation_datasets")
    cases: Mapped[list["EvaluationCase"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )
    runs: Mapped[list["EvaluationRun"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (Index("ix_evaluation_cases_dataset_created", "dataset_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    expected_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    dataset: Mapped[EvaluationDataset] = relationship(back_populates="cases")
    results: Mapped[list["EvaluationCaseResult"]] = relationship(
        back_populates="evaluation_case", passive_deletes=True
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_evaluation_runs_project_created", "project_id", "created_at"),
        Index("ix_evaluation_runs_dataset_created", "dataset_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_type: Mapped[EvaluationType] = mapped_column(
        Enum(EvaluationType, name="evaluation_type", native_enum=False)
    )
    status: Mapped[EvaluationRunStatus] = mapped_column(
        Enum(EvaluationRunStatus, name="evaluation_run_status", native_enum=False),
        default=EvaluationRunStatus.QUEUED,
    )
    prompt_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    embedding_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evaluator_version: Mapped[str] = mapped_column(String(50))
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    aggregate_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    error_cases: Mapped[int] = mapped_column(Integer, default=0)
    average_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    project: Mapped[Project] = relationship(back_populates="evaluation_runs")
    dataset: Mapped[EvaluationDataset] = relationship(back_populates="runs")
    prompt_version: Mapped["PromptVersion | None"] = relationship()
    case_results: Mapped[list["EvaluationCaseResult"]] = relationship(
        back_populates="evaluation_run", cascade="all, delete-orphan", passive_deletes=True
    )


class EvaluationCaseResult(Base):
    __tablename__ = "evaluation_case_results"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id", "evaluation_case_id", name="uq_evaluation_result_run_case"
        ),
        Index("ix_evaluation_case_results_run", "evaluation_run_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_case_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_cases.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[EvaluationCaseResultStatus] = mapped_column(
        Enum(
            EvaluationCaseResultStatus,
            name="evaluation_case_result_status",
            native_enum=False,
            length=10,
        )
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    case_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actual_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="case_results")
    evaluation_case: Mapped[EvaluationCase] = relationship(back_populates="results")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "sha256_hash", name="uq_documents_project_sha256"),
        Index("ix_documents_project_id", "project_id"),
        Index("ix_documents_sha256_hash", "sha256_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    storage_provider: Mapped[str] = mapped_column(String(40), default="local")
    storage_container: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.UPLOADED
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project: Mapped[Project] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    embedding_runs: Mapped[list["EmbeddingRun"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    chunk_embeddings: Mapped[list["DocumentChunkEmbedding"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    rag_questions: Mapped[list["RagQuestion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    character_count: Mapped[int] = mapped_column(Integer)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    document: Mapped[Document] = relationship(back_populates="chunks")
    extraction_evidence: Mapped[list["ExtractionEvidence"]] = relationship(
        back_populates="document_chunk", passive_deletes=True
    )
    embedding: Mapped["DocumentChunkEmbedding | None"] = relationship(
        back_populates="document_chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    rag_retrievals: Mapped[list["QuestionRetrievedChunk"]] = relationship(
        back_populates="chunk", passive_deletes=True
    )
    rag_citations: Mapped[list["RagCitation"]] = relationship(
        back_populates="chunk", passive_deletes=True
    )


class EmbeddingRun(Base):
    __tablename__ = "embedding_runs"
    __table_args__ = (Index("ix_embedding_runs_project_document", "project_id", "document_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EmbeddingRunStatus] = mapped_column(
        Enum(EmbeddingRunStatus, name="embedding_run_status"),
        default=EmbeddingRunStatus.QUEUED,
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int] = mapped_column(Integer)
    embedding_version: Mapped[str] = mapped_column(String(100))
    chunks_total: Mapped[int] = mapped_column(Integer, default=0)
    chunks_embedded: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    project: Mapped[Project] = relationship(back_populates="embedding_runs")
    document: Mapped[Document] = relationship(back_populates="embedding_runs")


class DocumentChunkEmbedding(Base):
    __tablename__ = "document_chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("document_chunk_id", name="uq_active_chunk_embedding"),
        Index(
            "ix_chunk_embeddings_scope_model",
            "project_id",
            "document_id",
            "provider",
            "model",
            "dimensions",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int] = mapped_column(Integer)
    embedding_version: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    document_chunk: Mapped[DocumentChunk] = relationship(back_populates="embedding")
    document: Mapped[Document] = relationship(back_populates="chunk_embeddings")


class RetrievalEvaluationRun(Base):
    __tablename__ = "retrieval_evaluation_runs"
    __table_args__ = (Index("ix_retrieval_evaluation_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(100))
    embedding_model: Mapped[str] = mapped_column(String(200))
    top_k: Mapped[int] = mapped_column(Integer)
    case_count: Mapped[int] = mapped_column(Integer)
    hit_rate: Mapped[float] = mapped_column()
    mean_reciprocal_rank: Mapped[float] = mapped_column()
    recall_at_k: Mapped[float] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    project: Mapped[Project] = relationship(back_populates="retrieval_evaluation_runs")
    case_results: Mapped[list["RetrievalEvaluationCaseResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class RetrievalEvaluationCaseResult(Base):
    __tablename__ = "retrieval_evaluation_case_results"
    __table_args__ = (Index("ix_retrieval_eval_cases_run", "run_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text)
    expected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    first_relevant_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hit: Mapped[bool] = mapped_column()
    recall: Mapped[float] = mapped_column()
    reciprocal_rank: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    run: Mapped[RetrievalEvaluationRun] = relationship(back_populates="case_results")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", passive_deletes=True
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_template_id", "version", name="uq_prompt_version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_template_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    template: Mapped[PromptTemplate] = relationship(back_populates="versions")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(back_populates="prompt_version")
    rag_questions: Mapped[list["RagQuestion"]] = relationship(back_populates="prompt_version")


class RagQuestion(Base):
    __tablename__ = "rag_questions"
    __table_args__ = (Index("ix_rag_questions_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[RagQuestionStatus] = mapped_column(
        Enum(RagQuestionStatus, name="rag_question_status"),
        default=RagQuestionStatus.QUEUED,
    )
    retrieval_top_k: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    project: Mapped[Project] = relationship(back_populates="rag_questions")
    document: Mapped[Document | None] = relationship(back_populates="rag_questions")
    prompt_version: Mapped[PromptVersion] = relationship(back_populates="rag_questions")
    answer: Mapped["RagAnswer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    retrieved_chunks: Mapped[list["QuestionRetrievedChunk"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", passive_deletes=True
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="rag_question", cascade="all, delete-orphan", passive_deletes=True
    )


class QuestionRetrievedChunk(Base):
    __tablename__ = "question_retrieved_chunks"
    __table_args__ = (
        UniqueConstraint("question_id", "chunk_id", name="uq_question_retrieved_chunk"),
        UniqueConstraint("question_id", "rank", name="uq_question_retrieved_rank"),
        Index("ix_question_retrieved_question", "question_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(
        ForeignKey("rag_questions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer)
    similarity_score: Mapped[float] = mapped_column(Float)
    embedding_provider: Mapped[str] = mapped_column(String(100))
    embedding_model: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    question: Mapped[RagQuestion] = relationship(back_populates="retrieved_chunks")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="rag_retrievals")
    document: Mapped[Document] = relationship()


class RagAnswer(Base):
    __tablename__ = "rag_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(
        ForeignKey("rag_questions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    answer_text: Mapped[str] = mapped_column(Text)
    support_status: Mapped[RagSupportStatus] = mapped_column(
        Enum(RagSupportStatus, name="rag_support_status")
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    question: Mapped[RagQuestion] = relationship(back_populates="answer")
    citations: Mapped[list["RagCitation"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan", passive_deletes=True
    )


class RagCitation(Base):
    __tablename__ = "rag_citations"
    __table_args__ = (Index("ix_rag_citations_answer", "answer_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id: Mapped[str] = mapped_column(
        ForeignKey("rag_answers.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer)
    similarity_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    answer: Mapped[RagAnswer] = relationship(back_populates="citations")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="rag_citations")
    document: Mapped[Document] = relationship()


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (Index("ix_extraction_runs_project_document", "project_id", "document_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ExtractionRunStatus] = mapped_column(
        Enum(ExtractionRunStatus, name="extraction_run_status"),
        default=ExtractionRunStatus.QUEUED,
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    project: Mapped[Project] = relationship(back_populates="extraction_runs")
    document: Mapped[Document] = relationship(back_populates="extraction_runs")
    prompt_version: Mapped[PromptVersion] = relationship(back_populates="extraction_runs")
    fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan", passive_deletes=True
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan", passive_deletes=True
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("extraction_run_id", "field_name", name="uq_extracted_field_run_name"),
        Index("ix_extracted_fields_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_run_id: Mapped[str] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100))
    field_type: Mapped[str] = mapped_column(String(50))
    raw_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    normalized_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    missing_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    corrected_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="field_review_status"), default=ReviewStatus.UNREVIEWED
    )
    support_status: Mapped[SupportStatus] = mapped_column(
        Enum(SupportStatus, name="field_support_status")
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    extraction_run: Mapped[ExtractionRun] = relationship(back_populates="fields")
    evidence: Mapped[list["ExtractionEvidence"]] = relationship(
        back_populates="extracted_field", cascade="all, delete-orphan", passive_deletes=True
    )


class ExtractionEvidence(Base):
    __tablename__ = "extraction_evidence"
    __table_args__ = (Index("ix_extraction_evidence_field_id", "extracted_field_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extracted_field_id: Mapped[str] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="CASCADE"), nullable=False
    )
    document_chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    extracted_field: Mapped[ExtractedField] = relationship(back_populates="evidence")
    document_chunk: Mapped[DocumentChunk] = relationship(back_populates="extraction_evidence")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_project_document", "project_id", "document_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=True
    )
    extracted_field_id: Mapped[str | None] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="CASCADE"), nullable=True
    )
    rag_question_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_questions.id", ondelete="CASCADE"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    extraction_run: Mapped[ExtractionRun | None] = relationship(back_populates="audit_events")
    rag_question: Mapped[RagQuestion | None] = relationship(back_populates="audit_events")
