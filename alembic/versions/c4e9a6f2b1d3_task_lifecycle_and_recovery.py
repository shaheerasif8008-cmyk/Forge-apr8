"""task_lifecycle_and_recovery

Revision ID: c4e9a6f2b1d3
Revises: 8f3a5c1d2b7e
Create Date: 2026-04-19 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e9a6f2b1d3"
down_revision: str | Sequence[str] | None = "8f3a5c1d2b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("input", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_type", sa.String(length=50), nullable=False, server_default="chat"),
        sa.Column(
            "input_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("response_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "result_card",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "workflow_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interruption_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_tasks_org_employee", "employee_tasks", ["org_id", "employee_id"])
    op.create_index("ix_employee_tasks_status", "employee_tasks", ["status"])
    op.create_index("ix_employee_tasks_conversation", "employee_tasks", ["conversation_id"])

    op.add_column(
        "deployments",
        sa.Column(
            "recovery_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "recovery_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("deployments", "recovery_state")
    op.drop_column("deployments", "recovery_policy")

    op.drop_index("ix_employee_tasks_conversation", table_name="employee_tasks")
    op.drop_index("ix_employee_tasks_status", table_name="employee_tasks")
    op.drop_index("ix_employee_tasks_org_employee", table_name="employee_tasks")
    op.drop_table("employee_tasks")
