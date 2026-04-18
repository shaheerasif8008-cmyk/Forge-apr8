"""reasoning_records

Revision ID: 2f6b2d7918be
Revises: 8f3a5c1d2b7e
Create Date: 2026-04-18 10:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2f6b2d7918be"
down_revision: str | Sequence[str] | None = "8f3a5c1d2b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reasoning_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("node_id", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("inputs_considered", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("modules_invoked", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("token_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reasoning_records_org_id", "reasoning_records", ["org_id"])
    op.create_index("ix_reasoning_records_employee_id", "reasoning_records", ["employee_id"])
    op.create_index("ix_reasoning_records_task_id", "reasoning_records", ["task_id"])
    op.create_index("ix_reasoning_records_node_id", "reasoning_records", ["node_id"])
    op.create_index(
        "uq_reasoning_records_task_node",
        "reasoning_records",
        ["task_id", "node_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_reasoning_records_task_node", table_name="reasoning_records")
    op.drop_index("ix_reasoning_records_node_id", table_name="reasoning_records")
    op.drop_index("ix_reasoning_records_task_id", table_name="reasoning_records")
    op.drop_index("ix_reasoning_records_employee_id", table_name="reasoning_records")
    op.drop_index("ix_reasoning_records_org_id", table_name="reasoning_records")
    op.drop_table("reasoning_records")
