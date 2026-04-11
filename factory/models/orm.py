"""SQLAlchemy 2.0 async ORM models for the Forge factory database.

Table mapping:
  client_orgs          ← ClientOrg
  clients              ← Client
  employee_requirements← EmployeeRequirements
  blueprints           ← EmployeeBlueprint
  builds               ← Build
  deployments          ← Deployment
  operational_memories ← employee runtime preference/fact store
  conversations        ← employee runtime conversation roots
  messages             ← employee runtime messages and approval records
  audit_events         ← append-only factory/runtime audit trail (hash-chained)

JSONB columns are used for any field that maps to a list[...] or dict[...] in
the Pydantic layer so we avoid row-per-item join tables at this stage.
All primary keys are UUID. Every table carries org_id for tenant isolation —
every query MUST filter by org_id.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Base ──────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── client_orgs ───────────────────────────────────────────────────────────────


class ClientOrgRow(Base):
    """Persists ClientOrg Pydantic model."""

    __tablename__ = "client_orgs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="enterprise")
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # relationships
    clients: Mapped[list[ClientRow]] = relationship(
        "ClientRow", back_populates="org", cascade="all, delete-orphan"
    )
    requirements: Mapped[list[EmployeeRequirementsRow]] = relationship(
        "EmployeeRequirementsRow", back_populates="org"
    )
    deployments: Mapped[list[DeploymentRow]] = relationship(
        "DeploymentRow", back_populates="org"
    )

    __table_args__ = (Index("ix_client_orgs_slug", "slug"),)


# ── clients ───────────────────────────────────────────────────────────────────


class ClientRow(Base):
    """Persists Client (individual user within an org)."""

    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    org: Mapped[ClientOrgRow] = relationship("ClientOrgRow", back_populates="clients")

    __table_args__ = (
        Index("ix_clients_org_id", "org_id"),
        Index("ix_clients_email", "email"),
    )


# ── employee_requirements ─────────────────────────────────────────────────────


class EmployeeRequirementsRow(Base):
    """Persists EmployeeRequirements (Analyst stage output).

    JSONB columns:
      primary_responsibilities  list[str]
      kpis                      list[str]
      required_tools            list[str]
      required_data_sources     list[str]
      communication_channels    list[str]
      compliance_frameworks     list[str]
      org_context               dict[str, str]
    """

    __tablename__ = "employee_requirements"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_orgs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # JSONB — list/dict fields
    primary_responsibilities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    kpis: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_data_sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    communication_channels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compliance_frameworks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    deployment_format: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    supervisor_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    org_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_intake: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    org: Mapped[ClientOrgRow] = relationship(
        "ClientOrgRow", back_populates="requirements"
    )
    blueprints: Mapped[list[BlueprintRow]] = relationship(
        "BlueprintRow", back_populates="requirements"
    )

    __table_args__ = (
        Index("ix_employee_requirements_org_id", "org_id"),
        Index("ix_employee_requirements_risk_tier", "risk_tier"),
    )


# ── blueprints ────────────────────────────────────────────────────────────────


class BlueprintRow(Base):
    """Persists EmployeeBlueprint (Architect stage output).

    JSONB columns:
      components          list[SelectedComponent]  — full nested structure
      custom_code_specs   list[CustomCodeSpec]
      autonomy_profile    dict[str, Any]
    """

    __tablename__ = "blueprints"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    requirements_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employee_requirements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSONB — nested Pydantic model lists and dicts
    components: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    custom_code_specs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    workflow_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    autonomy_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estimated_cost_per_task_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    architect_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    requirements: Mapped[EmployeeRequirementsRow] = relationship(
        "EmployeeRequirementsRow", back_populates="blueprints"
    )
    builds: Mapped[list[BuildRow]] = relationship(
        "BuildRow", back_populates="blueprint"
    )

    __table_args__ = (
        Index("ix_blueprints_org_id", "org_id"),
        Index("ix_blueprints_requirements_id", "requirements_id"),
    )


# ── builds ────────────────────────────────────────────────────────────────────


class BuildRow(Base):
    """Persists Build (Builder + Evaluator stage record).

    JSONB columns:
      logs         list[BuildLog]      — all stage log entries
      artifacts    list[BuildArtifact] — container images, bundles, reports
      test_report  dict[str, Any]      — evaluator output
    """

    __tablename__ = "builds"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    requirements_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employee_requirements.id", ondelete="SET NULL"),
        nullable=True,
    )
    blueprint_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("blueprints.id", ondelete="RESTRICT"),
        nullable=True,
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # JSONB — structured log/artifact arrays + test report blob
    logs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    artifacts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    test_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    blueprint: Mapped[BlueprintRow] = relationship(
        "BlueprintRow", back_populates="builds"
    )
    deployment: Mapped[DeploymentRow | None] = relationship(
        "DeploymentRow", back_populates="build", uselist=False
    )

    __table_args__ = (
        Index("ix_builds_org_id", "org_id"),
        Index("ix_builds_requirements_id", "requirements_id"),
        Index("ix_builds_blueprint_id", "blueprint_id"),
        Index("ix_builds_status", "status"),
    )


# ── deployments ───────────────────────────────────────────────────────────────


class DeploymentRow(Base):
    """Persists Deployment (Deployer stage record).

    JSONB column:
      infrastructure  dict[str, Any] — provider, region, resource IDs
    """

    __tablename__ = "deployments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    build_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,  # one deployment per build
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_orgs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    access_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    infrastructure: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    health_last_checked: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    build: Mapped[BuildRow] = relationship("BuildRow", back_populates="deployment")
    org: Mapped[ClientOrgRow] = relationship("ClientOrgRow", back_populates="deployments")

    __table_args__ = (
        Index("ix_deployments_org_id", "org_id"),
        Index("ix_deployments_status", "status"),
    )


# ── operational_memories ─────────────────────────────────────────────────────


class OperationalMemoryRow(Base):
    """Persistent runtime facts and employee settings scoped by org + employee."""

    __tablename__ = "operational_memories"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    __table_args__ = (
        Index("idx_opmem_lookup", "org_id", "employee_id", "key"),
        Index("idx_opmem_category", "org_id", "employee_id", "category"),
        Index("ix_operational_memories_org_id", "org_id"),
        Index(
            "uq_operational_memories_scope",
            "org_id",
            "employee_id",
            "key",
            unique=True,
        ),
    )


# ── conversations ────────────────────────────────────────────────────────────


class ConversationRow(Base):
    """Conversation root for a deployed employee."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    messages: Mapped[list["MessageRow"]] = relationship(
        "MessageRow", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_org_employee", "org_id", "employee_id"),)


# ── messages ─────────────────────────────────────────────────────────────────


class MessageRow(Base):
    """Conversation message, including approval and status messages."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[ConversationRow] = relationship(
        "ConversationRow", back_populates="messages"
    )

    __table_args__ = (Index("idx_messages_conv", "conversation_id", "created_at"),)


# ── audit_events ──────────────────────────────────────────────────────────────


class AuditEventRow(Base):
    """Append-only, hash-chained factory audit trail.

    Rules (from CLAUDE.md architecture invariants):
      - Append-only: no UPDATE or DELETE ever touches this table.
      - hash_chain links each event to its predecessor for tamper evidence.
      - Every pipeline stage, design decision, tool call, and approval is recorded.
      - org_id is mandatory — every audit query must scope by tenant.

    JSONB column:
      detail  dict[str, Any] — arbitrary event-specific payload
    """

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    # entity being audited — any table/row
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # actor
    actor: Mapped[str] = mapped_column(
        String(100), nullable=False, default="factory"
    )
    employee_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # action performed
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # arbitrary structured payload
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # hash chain — sha256(prev_hash + this event payload)
    hash_chain: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # timestamp is server-side and not overridable by application code
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_events_org_id", "org_id"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_employee_id", "employee_id"),
        Index("ix_audit_events_event_type", "event_type"),
    )

    @staticmethod
    def compute_hash(prev_hash: str, event_payload: dict) -> str:
        """Compute sha256(prev_hash + sorted JSON payload) for chain integrity.

        Args:
            prev_hash: Hash of the immediately preceding event for this entity,
                or empty string for the first event.
            event_payload: The detail dict that will be stored in this event.

        Returns:
            Hex-encoded SHA-256 digest to store in hash_chain.
        """
        raw = prev_hash + json.dumps(event_payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()
