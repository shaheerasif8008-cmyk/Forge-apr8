"""Typed schemas for the Phase 1 legal intake vertical slice."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class LegalIntakeInput(BaseModel):
    email_text: str


class LegalIntakeExtraction(BaseModel):
    """Structured extraction from a legal intake email."""

    client_name: str = ""
    client_email: str = ""
    client_phone: str = ""
    matter_type: str = ""
    date_of_incident: str = ""
    opposing_party: str = ""
    key_facts: list[str] = Field(default_factory=list)
    urgency: str = "normal"
    potential_conflicts: list[str] = Field(default_factory=list)
    estimated_value: str = ""
    referral_source: str = ""
    raw_summary: str = ""
    extraction_confidence: float = 0.0


class AnalysisInput(BaseModel):
    extraction: LegalIntakeExtraction


class DocumentAnalyzerOutput(BaseModel):
    summary: str
    key_findings: list[str]
    risk_flags: list[str]
    recommended_actions: list[str]
    qualification_decision: str
    qualification_reasoning: str
    confidence: float


class ConfidenceInput(BaseModel):
    extraction: LegalIntakeExtraction
    analysis: DocumentAnalyzerOutput


class ConfidenceReport(BaseModel):
    overall_score: float
    llm_self_assessment: float
    structural_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    recommendation: str


class DraftInput(BaseModel):
    extraction: LegalIntakeExtraction
    analysis: DocumentAnalyzerOutput
    confidence_report: ConfidenceReport


class IntakeBrief(BaseModel):
    brief_id: str = Field(default_factory=lambda: str(uuid4()))
    client_info: LegalIntakeExtraction
    analysis: DocumentAnalyzerOutput
    confidence_score: float
    executive_summary: str = ""
    recommended_attorney: str = ""
    recommended_practice_area: str = ""
    next_steps: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class InputProtectionResult(BaseModel):
    is_safe: bool
    risk_score: float
    flags: list[str] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    sanitized_input: str


class VerificationInput(BaseModel):
    brief: IntakeBrief


class VerificationResult(BaseModel):
    is_valid: bool
    flags: list[str] = Field(default_factory=list)
    normalized_fields: dict[str, str] = Field(default_factory=dict)


class ChainVerification(BaseModel):
    valid: bool
    checked_events: int
    failure_reason: str = ""


class ExecutiveAssistantInput(BaseModel):
    request_text: str
    sender: str = ""
    channel: str = "chat"


class ExecutiveAssistantPlan(BaseModel):
    summary: str
    requested_actions: list[str] = Field(default_factory=list)
    finance_actions: list[str] = Field(default_factory=list)
    finance_summary: str = ""
    finance_metrics: dict[str, float] = Field(default_factory=dict)
    stakeholders: list[str] = Field(default_factory=list)
    meeting_topics: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    rationale: str = ""
    is_novel_situation: bool = False
    novel_options: list[dict[str, str]] = Field(default_factory=list)
    recommended_option: str = ""
    guidance_request: str = ""
    novel_trigger: str = ""


class ExecutiveAssistantResult(BaseModel):
    title: str
    summary: str
    drafted_response: str = ""
    action_items: list[str] = Field(default_factory=list)
    finance_actions: list[str] = Field(default_factory=list)
    schedule_updates: list[str] = Field(default_factory=list)
    crm_updates: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    novel_options: list[dict[str, str]] = Field(default_factory=list)
    recommended_option: str = ""
    needs_guidance: bool = False


class ResearchRequest(BaseModel):
    question: str
    sources: list[str] = Field(default_factory=lambda: ["web"])
    documents: list[str] = Field(default_factory=list)
    max_results: int = 5
    metadata_filters: dict[str, str] = Field(default_factory=dict)
    notes: str = ""


class Finding(BaseModel):
    statement: str
    rationale: str = ""
    citations: list[str] = Field(default_factory=list)
    source_type: str = ""
    confidence: float = 0.0


class ResearchReport(BaseModel):
    question: str
    sources_used: list[str] = Field(default_factory=list)
    key_findings: list[Finding] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class DataAnalysisRequest(BaseModel):
    csv_data: str | None = None
    source_csvs: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    sql_query: str | None = None
    question: str = ""
    max_anomalies: int = 3


class DataColumnProfile(BaseModel):
    name: str
    inferred_type: str
    null_count: int = 0
    unique_values: int = 0


class DataReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: list[DataColumnProfile] = Field(default_factory=list, alias="schema")
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[str] = Field(default_factory=list)
    narrative_summary: str = ""

    @property
    def schema(self) -> list[DataColumnProfile]:
        return self.schema_


class ScanRequest(BaseModel):
    source: str
    query: str = ""
    criteria: list[str] = Field(default_factory=list)
    limit: int = 10
    source_config: dict[str, Any] = Field(default_factory=dict)
    raw_items: list[dict[str, Any]] = Field(default_factory=list)


class Signal(BaseModel):
    source: str
    content: str
    timestamp: str = ""
    raw_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
