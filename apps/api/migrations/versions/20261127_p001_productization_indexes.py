"""Add indexes for product workspace queries.

Revision ID: 20261127_p001
Revises: 20261126_0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261127_p001"
down_revision: str | None = "20261126_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_project_status_created",
        "documents",
        ["project_id", "status", "created_at"],
    )
    op.create_index(
        "ix_extracted_fields_review_updated",
        "extracted_fields",
        ["review_status", "updated_at"],
    )
    op.create_index(
        "ix_rag_questions_project_document_created",
        "rag_questions",
        ["project_id", "document_id", "created_at"],
    )
    op.create_index(
        "ix_rag_answers_support_question",
        "rag_answers",
        ["support_status", "question_id"],
    )
    op.create_index(
        "ix_evaluation_runs_project_type_status_created",
        "evaluation_runs",
        ["project_id", "evaluation_type", "status", "created_at"],
    )
    op.create_index(
        "ix_audit_events_project_created",
        "audit_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_project_event_created",
        "audit_events",
        ["project_id", "event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_project_event_created", table_name="audit_events")
    op.drop_index("ix_audit_events_project_created", table_name="audit_events")
    op.drop_index("ix_evaluation_runs_project_type_status_created", table_name="evaluation_runs")
    op.drop_index("ix_rag_answers_support_question", table_name="rag_answers")
    op.drop_index("ix_rag_questions_project_document_created", table_name="rag_questions")
    op.drop_index("ix_extracted_fields_review_updated", table_name="extracted_fields")
    op.drop_index("ix_documents_project_status_created", table_name="documents")
