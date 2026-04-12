"""runtime_phase1

Revision ID: 67f0237b4df9
Revises: 3d781c3d720f
Create Date: 2026-04-10 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "67f0237b4df9"
down_revision: str | Sequence[str] | None = "3d781c3d720f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="general"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "employee_id", "key", name="uq_operational_memories_scope"),
    )
    op.create_index(
        "idx_opmem_lookup", "operational_memories", ["org_id", "employee_id", "key"]
    )
    op.create_index(
        "idx_opmem_category", "operational_memories", ["org_id", "employee_id", "category"]
    )
    op.create_index("ix_operational_memories_org_id", "operational_memories", ["org_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_org_employee", "conversations", ["org_id", "employee_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False, server_default="text"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_messages_conv", "messages", ["conversation_id", "created_at"])

    op.add_column("audit_events", sa.Column("employee_id", sa.String(length=255), nullable=True))
    op.add_column("audit_events", sa.Column("event_type", sa.String(length=100), nullable=True))
    op.add_column(
        "audit_events",
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "audit_events",
        sa.Column("prev_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "audit_events",
        sa.Column("hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column("audit_events", sa.Column("trace_id", sa.String(length=255), nullable=True))
    op.create_index("ix_audit_events_employee_id", "audit_events", ["employee_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_employee_id", table_name="audit_events")
    op.drop_column("audit_events", "trace_id")
    op.drop_column("audit_events", "hash")
    op.drop_column("audit_events", "prev_hash")
    op.drop_column("audit_events", "details")
    op.drop_column("audit_events", "event_type")
    op.drop_column("audit_events", "employee_id")

    op.drop_index("idx_messages_conv", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_org_employee", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_operational_memories_org_id", table_name="operational_memories")
    op.drop_index("idx_opmem_category", table_name="operational_memories")
    op.drop_index("idx_opmem_lookup", table_name="operational_memories")
    op.drop_table("operational_memories")
