"""Add pgvector embeddings, embedding runs, and retrieval evaluation.

Revision ID: 20261110_0003
Revises: 20261107_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20261110_0003"
down_revision: str | None = "20261107_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

embedding_run_status = sa.Enum(
    "QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="embedding_run_status"
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_run_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "embedding_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", embedding_run_status, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("chunks_total", sa.Integer(), nullable=False),
        sa.Column("chunks_embedded", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_embedding_runs_project_document",
        "embedding_runs",
        ["project_id", "document_id"],
    )
    op.create_table(
        "document_chunk_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_chunk_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_chunk_id", name="uq_active_chunk_embedding"),
    )
    op.create_index(
        "ix_chunk_embeddings_scope_model",
        "document_chunk_embeddings",
        ["project_id", "document_id", "provider", "model", "dimensions"],
    )
    op.create_table(
        "retrieval_evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_provider", sa.String(length=100), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("hit_rate", sa.Float(), nullable=False),
        sa.Column("mean_reciprocal_rank", sa.Float(), nullable=False),
        sa.Column("recall_at_k", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_evaluation_project",
        "retrieval_evaluation_runs",
        ["project_id"],
    )
    op.create_table(
        "retrieval_evaluation_case_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("first_relevant_rank", sa.Integer(), nullable=True),
        sa.Column("hit", sa.Boolean(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("reciprocal_rank", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["retrieval_evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_eval_cases_run",
        "retrieval_evaluation_case_results",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_eval_cases_run", table_name="retrieval_evaluation_case_results")
    op.drop_table("retrieval_evaluation_case_results")
    op.drop_index("ix_retrieval_evaluation_project", table_name="retrieval_evaluation_runs")
    op.drop_table("retrieval_evaluation_runs")
    op.drop_index("ix_chunk_embeddings_scope_model", table_name="document_chunk_embeddings")
    op.drop_table("document_chunk_embeddings")
    op.drop_index("ix_embedding_runs_project_document", table_name="embedding_runs")
    op.drop_table("embedding_runs")
    embedding_run_status.drop(op.get_bind(), checkfirst=True)
