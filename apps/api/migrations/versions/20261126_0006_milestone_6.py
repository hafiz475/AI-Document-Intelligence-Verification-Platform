"""Add production identity, membership, storage, and audit metadata.

Revision ID: 20261126_0006
Revises: 20261125_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_0006"
down_revision: str | None = "20261125_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_subject", name="uq_users_external_subject"),
    )
    op.create_table(
        "project_memberships",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('OWNER', 'EDITOR', 'VIEWER')", name="ck_membership_role"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )
    op.create_index(
        "ix_project_memberships_user_project",
        "project_memberships",
        ["user_id", "project_id"],
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column(
            "project_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "storage_provider", sa.String(length=40), nullable=False, server_default="local"
            )
        )
        batch.add_column(sa.Column("storage_container", sa.String(length=255), nullable=True))
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("actor_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("target_type", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("target_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("request_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("trace_id", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_audit_events_actor_user_id", "users", ["actor_user_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index(
        "ix_audit_events_actor_created", "audit_events", ["actor_user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_actor_created", table_name="audit_events")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("fk_audit_events_actor_user_id", type_="foreignkey")
        batch.drop_column("trace_id")
        batch.drop_column("request_id")
        batch.drop_column("target_id")
        batch.drop_column("target_type")
        batch.drop_column("actor_user_id")
    op.execute(
        sa.delete(sa.table("audit_events", sa.column("project_id"))).where(
            sa.column("project_id").is_(None)
        )
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column(
            "project_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("storage_container")
        batch.drop_column("storage_provider")
    op.drop_index("ix_project_memberships_user_project", table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_table("users")
