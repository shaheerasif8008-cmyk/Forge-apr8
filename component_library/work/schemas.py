"""Typed schemas for the Phase 1 legal intake vertical slice."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InputProtectionResult(BaseModel):
    is_safe: bool
    risk_score: float
    flags: list[str] = Field(default_factory=list)
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
