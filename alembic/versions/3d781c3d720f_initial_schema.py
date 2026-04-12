"""initial_schema

Revision ID: 3d781c3d720f
Revises:
Create Date: 2026-04-09 21:24:36.395856

Creates all Forge factory tables from scratch.  This migration assumes a clean
database — it does NOT drop any pre-existing tables from other projects.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d781c3d720f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all factory tables."""

    # ── audit_events ──────────────────────────────────────────────
    # Created first — no FK dependencies — append-only audit trail.
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False, server_default="factory"),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("hash_chain", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_org_id", "audit_events", ["org_id"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])

    # ── client_orgs ───────────────────────────────────────────────
    op.create_table(
        "client_orgs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("tier", sa.String(length=50), nullable=False, server_default="enterprise"),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_client_orgs_slug", "client_orgs", ["slug"])

    # ── clients ───────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="owner"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_org_id", "clients", ["org_id"])
    op.create_index("ix_clients_email", "clients", ["email"])

    # ── employee_requirements ─────────────────────────────────────
    op.create_table(
        "employee_requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role_summary", sa.Text(), nullable=False, server_default=""),
        # JSONB list/dict columns
        sa.Column(
            "primary_responsibilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "kpis",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "required_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "required_data_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "communication_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "compliance_frameworks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("risk_tier", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column(
            "deployment_format", sa.String(length=20), nullable=False, server_default="web"
        ),
        sa.Column("supervisor_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column(
            "org_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("raw_intake", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_requirements_org_id", "employee_requirements", ["org_id"])
    op.create_index(
        "ix_employee_requirements_risk_tier", "employee_requirements", ["risk_tier"]
    )

    # ── blueprints ────────────────────────────────────────────────
    op.create_table(
        "blueprints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requirements_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_name", sa.String(length=255), nullable=False),
        # JSONB — nested Pydantic lists
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "custom_code_specs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("workflow_description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "autonomy_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("estimated_cost_per_task_usd", sa.Float(), nullable=True),
        sa.Column("architect_reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["requirements_id"], ["employee_requirements.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blueprints_org_id", "blueprints", ["org_id"])
    op.create_index("ix_blueprints_requirements_id", "blueprints", ["requirements_id"])

    # ── builds ────────────────────────────────────────────────────
    op.create_table(
        "builds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("blueprint_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="1"),
        # JSONB — logs array, artifacts array, test report blob
        sa.Column(
            "logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "artifacts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "test_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["blueprint_id"], ["blueprints.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_builds_org_id", "builds", ["org_id"])
    op.create_index("ix_builds_blueprint_id", "builds", ["blueprint_id"])
    op.create_index("ix_builds_status", "builds", ["status"])

    # ── deployments ───────────────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("build_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False, server_default="web"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("access_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column(
            "infrastructure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("health_last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["org_id"], ["client_orgs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_id"),
    )
    op.create_index("ix_deployments_org_id", "deployments", ["org_id"])
    op.create_index("ix_deployments_status", "deployments", ["status"])


def downgrade() -> None:
    """Drop all factory tables in reverse FK order."""
    op.drop_table("deployments")
    op.drop_table("builds")
    op.drop_table("blueprints")
    op.drop_table("employee_requirements")
    op.drop_table("clients")
    op.drop_table("client_orgs")
    op.drop_table("audit_events")
