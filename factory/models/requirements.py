"""Employee requirements document — output of the Analyst stage."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ComplianceFramework(str, Enum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    FEDRAMP = "fedramp"
    GDPR = "gdpr"
    NONE = "none"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmployeeRequirements(BaseModel):
    """Structured requirements produced by the Analyst AI after client intake."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    name: str = Field(description="Employee name, e.g. 'Legal Intake Agent'")
    role_summary: str = Field(description="One-paragraph description of the employee's purpose")
    primary_responsibilities: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list, description="Measurable success metrics")
    required_tools: list[str] = Field(default_factory=list)
    required_data_sources: list[str] = Field(default_factory=list)
    communication_channels: list[str] = Field(default_factory=list)
    compliance_frameworks: list[ComplianceFramework] = Field(default_factory=list)
    risk_tier: RiskTier = RiskTier.MEDIUM
    deployment_format: str = Field("web", description="web | desktop | server")
    supervisor_email: str = Field("")
    org_context: dict[str, str] = Field(
        default_factory=dict,
        description="People and roles the employee interacts with",
    )
    raw_intake: str = Field("", description="Original client description (preserved for audit)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
