"""Runtime-owned ORM models used by packaged employees and shared components."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ClientOrgRow(Base):
    __tablename__ = "client_orgs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="enterprise")
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_client_orgs_slug", "slug"),)


class OperationalMemoryRow(Base):
    __tablename__ = "operational_memories"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("client_orgs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
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
        Index("uq_operational_memories_scope", "org_id", "employee_id", "key", unique=True),
    )


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("client_orgs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    messages: Mapped[list["MessageRow"]] = relationship("MessageRow", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_conversations_org_employee", "org_id", "employee_id"),)


class EmployeeTaskRow(Base):
    __tablename__ = "employee_tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("client_orgs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_type: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    input_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_card: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    workflow_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interruption_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    conversation: Mapped[ConversationRow | None] = relationship("ConversationRow")

    __table_args__ = (
        Index("ix_employee_tasks_org_employee", "org_id", "employee_id"),
        Index("ix_employee_tasks_status", "status"),
        Index("ix_employee_tasks_conversation", "conversation_id"),
    )


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    message_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    conversation: Mapped[ConversationRow] = relationship("ConversationRow", back_populates="messages")

    __table_args__ = (Index("idx_messages_conv", "conversation_id", "created_at"),)


class ReasoningRecordRow(Base):
    __tablename__ = "reasoning_records"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("client_orgs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inputs_considered: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    modules_invoked: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    token_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_reasoning_records_org_id", "org_id"),
        Index("ix_reasoning_records_employee_id", "employee_id"),
        Index("ix_reasoning_records_task_id", "task_id"),
        Index("ix_reasoning_records_node_id", "node_id"),
        Index("uq_reasoning_records_task_node", "task_id", "node_id", unique=True),
    )


class KnowledgeChunkRow(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_knowledge_chunks_tenant_id", "tenant_id"),
        Index("ix_knowledge_chunks_tenant_document", "tenant_id", "document_id"),
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="employee_runtime")
    employee_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash_chain: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_events_org_id", "org_id"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_employee_id", "employee_id"),
        Index("ix_audit_events_event_type", "event_type"),
    )

    @staticmethod
    def compute_hash(prev_hash: str, event_payload: dict) -> str:
        raw = prev_hash + json.dumps(event_payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()
