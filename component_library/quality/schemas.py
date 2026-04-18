"""Shared schemas for quality and governance components."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProposedAction(BaseModel):
    type: Literal["reversible", "semi_reversible", "irreversible"]
    description: str
    confidence: float
    estimated_impact: dict[str, Any] = Field(default_factory=dict)


class AutonomyContext(BaseModel):
    risk_tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    tenant_policy: dict[str, Any] = Field(default_factory=dict)


class AutonomyDecision(BaseModel):
    mode: Literal["autonomous", "approval_required", "escalate"]
    required_approver: str | None = None
    rationale: str
    matched_rule: str


class Alternative(BaseModel):
    option: str
    score: float
    why_not_chosen: str


class EvidenceSource(BaseModel):
    source_type: str
    reference: str
    content_snippet: str


class DecisionPoint(BaseModel):
    task_id: UUID
    node_id: str
    decision: str
    rationale: str
    inputs_considered: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[Alternative] = Field(default_factory=list)
    evidence: list[EvidenceSource] = Field(default_factory=list)
    confidence: float = 0.0
    modules_invoked: list[str] = Field(default_factory=list)
    token_cost: int = 0
    latency_ms: int = 0


class ReasoningRecord(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    node_id: str
    decision: str
    rationale: str
    inputs_considered: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[Alternative] = Field(default_factory=list)
    evidence: list[EvidenceSource] = Field(default_factory=list)
    confidence: float = 0.0
    modules_invoked: list[str] = Field(default_factory=list)
    token_cost: int = 0
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyDecision(BaseModel):
    allowed: bool
    violations: list[str] = Field(default_factory=list)
    required_remediation: list[str] = Field(default_factory=list)
