"""Employee requirements document — output of the Analyst stage."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class EmployeeArchetype(str, Enum):
    LEGAL_INTAKE_ASSOCIATE = "legal_intake_associate"
    EXECUTIVE_ASSISTANT = "executive_assistant"


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


class AuthorityLevel(str, Enum):
    AUTONOMOUS = "autonomous"
    REQUIRES_APPROVAL = "requires_approval"
    NEVER_DO_ALONE = "never_do_alone"


class OrgRelationship(str, Enum):
    SUPERVISOR = "supervisor"
    COLLEAGUE = "colleague"
    REPORT = "report"
    ESCALATION = "escalation"


class OrgContact(BaseModel):
    name: str
    role: str
    email: str = ""
    preferred_channel: str = "email"
    communication_style: str = "concise"
    relationship: OrgRelationship = OrgRelationship.COLLEAGUE


class CommunicationRule(BaseModel):
    name: str
    description: str
    channel: str = "app"
    condition: str = ""
    action: str = ""
    priority: int = 2


class MonitoringPreferences(BaseModel):
    morning_briefing_enabled: bool = True
    drift_detection_enabled: bool = True
    health_check_interval_minutes: int = 15
    alert_channels: list[str] = Field(default_factory=lambda: ["email"])


class UpdatePreferences(BaseModel):
    security_auto_apply: bool = True
    learning_enabled: bool = True
    module_upgrade_mode: str = "preview"
    marketplace_opt_in: bool = False
    policy_source: str = "portal"


class EmployeeRequirements(BaseModel):
    """Structured requirements produced by the Analyst AI after client intake."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    employee_type: EmployeeArchetype = EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
    name: str = Field(description="Employee name, e.g. 'Legal Intake Agent'")
    role_title: str = Field("", description="Human-readable role title shown to the client")
    role_summary: str = Field(description="One-paragraph description of the employee's purpose")
    primary_responsibilities: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list, description="Measurable success metrics")
    required_tools: list[str] = Field(default_factory=list)
    required_data_sources: list[str] = Field(default_factory=list)
    communication_channels: list[str] = Field(default_factory=list)
    compliance_frameworks: list[ComplianceFramework] = Field(default_factory=list)
    risk_tier: RiskTier = RiskTier.MEDIUM
    deployment_format: str = Field("web", description="web | desktop | server")
    deployment_target: str = Field("hosted_web", description="hosted_web | desktop | server")
    supervisor_email: str = Field("")
    org_context: dict[str, object] = Field(
        default_factory=dict,
        description="People and roles the employee interacts with",
    )
    org_map: list[OrgContact] = Field(default_factory=list)
    authority_matrix: dict[str, AuthorityLevel] = Field(default_factory=dict)
    communication_rules: list[CommunicationRule] = Field(default_factory=list)
    monitoring_preferences: MonitoringPreferences = Field(default_factory=MonitoringPreferences)
    update_preferences: UpdatePreferences = Field(default_factory=UpdatePreferences)
    raw_intake: str = Field("", description="Original client description (preserved for audit)")
    created_at: datetime = Field(default_factory=utc_now)
