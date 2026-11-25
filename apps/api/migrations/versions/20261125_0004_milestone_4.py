"""Add evidence-backed RAG questions, answers, citations, and provenance.

Revision ID: 20261125_0004
Revises: 20261110_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261125_0004"
down_revision: str | None = "20261110_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

rag_question_status = sa.Enum(
    "QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="rag_question_status"
)
rag_support_status = sa.Enum(
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    name="rag_support_status",
)


def upgrade() -> None:
    op.create_table(
        "rag_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", rag_question_status, nullable=False),
        sa.Column("retrieval_top_k", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rag_questions_project_created",
        "rag_questions",
        ["project_id", "created_at"],
    )
    op.create_table(
        "question_retrieved_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=100), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_id"], ["rag_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "chunk_id", name="uq_question_retrieved_chunk"),
        sa.UniqueConstraint("question_id", "rank", name="uq_question_retrieved_rank"),
    )
    op.create_index(
        "ix_question_retrieved_question",
        "question_retrieved_chunks",
        ["question_id"],
    )
    op.create_table(
        "rag_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("support_status", rag_support_status, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["rag_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id"),
    )
    op.create_table(
        "rag_citations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["rag_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_citations_answer", "rag_citations", ["answer_id"])

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column("document_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.add_column(sa.Column("rag_question_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_audit_events_rag_question_id",
            "rag_questions",
            ["rag_question_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    op.execute("DELETE FROM audit_events WHERE rag_question_id IS NOT NULL")
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_constraint("fk_audit_events_rag_question_id", type_="foreignkey")
        batch_op.drop_column("rag_question_id")
        batch_op.alter_column("document_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_index("ix_rag_citations_answer", table_name="rag_citations")
    op.drop_table("rag_citations")
    op.drop_table("rag_answers")
    op.drop_index("ix_question_retrieved_question", table_name="question_retrieved_chunks")
    op.drop_table("question_retrieved_chunks")
    op.drop_index("ix_rag_questions_project_created", table_name="rag_questions")
    op.drop_table("rag_questions")
    rag_support_status.drop(op.get_bind(), checkfirst=True)
    rag_question_status.drop(op.get_bind(), checkfirst=True)
