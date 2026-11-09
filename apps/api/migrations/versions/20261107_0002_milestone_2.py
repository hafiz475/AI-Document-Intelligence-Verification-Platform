"""Add structured extraction, evidence, prompt, review, and audit persistence."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0002"
down_revision: str | None = "20261106_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROMPT_TEMPLATE_ID = "8be662d8-6eb8-4e93-8708-482a067d985f"
PROMPT_VERSION_ID = "f7190edc-09a7-4a3c-b1c0-462a6c79493b"
PROMPT_CONTENT = """You extract structured facts from engineering and inspection
reports.

Rules:
- Extract only facts directly supported by the supplied source chunks.
- Never guess, infer, or complete missing information.
- For absent information, return null and a concise missing_reason such as "not_found".
- Evidence may reference only CHUNK_ID values supplied in the input.
- Copy short evidence quotes from the referenced chunk. Never invent a quote.
- Do not return page numbers. The application derives pages from validated chunks.
- Preserve engineering terminology and identifiers exactly.
- Use ISO YYYY-MM-DD dates only when the source supplies an unambiguous date.
- Obey the required schema for every field.
"""


def upgrade() -> None:
    extraction_status = sa.Enum(
        "QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="extraction_run_status"
    )
    review_status = sa.Enum(
        "UNREVIEWED", "VERIFIED", "CORRECTED", "REJECTED", name="field_review_status"
    )
    support_status = sa.Enum(
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        name="field_support_status",
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"], ["prompt_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_template_id", "version", name="uq_prompt_version_number"),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "prompt_templates",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": PROMPT_TEMPLATE_ID,
                "name": "Inspection Extraction Prompt",
                "description": "Structured extraction for engineering and inspection reports.",
                "created_at": now,
            }
        ],
    )
    op.bulk_insert(
        sa.table(
            "prompt_versions",
            sa.column("id", sa.String),
            sa.column("prompt_template_id", sa.String),
            sa.column("version", sa.Integer),
            sa.column("content", sa.Text),
            sa.column("schema_version", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": PROMPT_VERSION_ID,
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "version": 1,
                "content": PROMPT_CONTENT,
                "schema_version": "inspection-extraction-v1",
                "created_at": now,
            }
        ],
    )

    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", extraction_status, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_runs_project_document",
        "extraction_runs",
        ["project_id", "document_id"],
    )
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("field_type", sa.String(length=50), nullable=False),
        sa.Column("raw_value", sa.JSON(), nullable=True),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("missing_reason", sa.String(length=200), nullable=True),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("review_status", review_status, nullable=False),
        sa.Column("support_status", support_status, nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("extraction_run_id", "field_name", name="uq_extracted_field_run_name"),
    )
    op.create_index("ix_extracted_fields_document_id", "extracted_fields", ["document_id"])
    op.create_table(
        "extraction_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("extracted_field_id", sa.String(length=36), nullable=False),
        sa.Column("document_chunk_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extracted_field_id"], ["extracted_fields.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_evidence_field_id",
        "extraction_evidence",
        ["extracted_field_id"],
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=36), nullable=True),
        sa.Column("extracted_field_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("reviewer", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extracted_field_id"], ["extracted_fields.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_project_document",
        "audit_events",
        ["project_id", "document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_project_document", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_extraction_evidence_field_id", table_name="extraction_evidence")
    op.drop_table("extraction_evidence")
    op.drop_index("ix_extracted_fields_document_id", table_name="extracted_fields")
    op.drop_table("extracted_fields")
    op.drop_index("ix_extraction_runs_project_document", table_name="extraction_runs")
    op.drop_table("extraction_runs")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_templates")
    bind = op.get_bind()
    sa.Enum(name="field_support_status").drop(bind, checkfirst=True)
    sa.Enum(name="field_review_status").drop(bind, checkfirst=True)
    sa.Enum(name="extraction_run_status").drop(bind, checkfirst=True)
