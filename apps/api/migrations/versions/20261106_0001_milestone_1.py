"""Create projects, documents, and document chunks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    document_status = sa.Enum(
        "UPLOADED", "QUEUED", "PROCESSING", "READY", "FAILED", name="document_status"
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sha256_hash", name="uq_documents_project_sha256"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_sha256_hash", "documents", ["sha256_hash"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_sha256_hash", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("projects")
