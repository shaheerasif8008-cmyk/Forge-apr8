"""Employee blueprint — output of the Architect stage."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from factory.models.requirements import EmployeeArchetype


class SelectedComponent(BaseModel):
    """A single component selected from the library for this employee."""

    category: str = Field(description="models | work | tools | data | quality")
    component_id: str
    version: str = "latest"
    config: dict[str, object] = Field(default_factory=dict)


class CustomCodeSpec(BaseModel):
    """Specification for code that must be generated (no library component covers it)."""

    name: str
    description: str
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)


class IdentityLayerInputs(BaseModel):
    core_identity: str = ""
    role_definition: str = ""
    organizational_map: str = ""
    behavioral_rules: str = ""
    retrieved_context: str = ""
    self_awareness: str = ""


class MonitoringPolicy(BaseModel):
    health_check_interval_minutes: int = 15
    drift_detection_enabled: bool = True
    alert_channels: list[str] = Field(default_factory=list)


class DeploymentSpec(BaseModel):
    format: str = "web"
    target: str = "hosted_web"
    hosted_base_url: str = ""


class UIProfile(BaseModel):
    app_title: str = ""
    app_badge: str = ""
    primary_channel_label: str = "Employee App"
    capabilities: list[str] = Field(default_factory=list)


class EmployeeBlueprint(BaseModel):
    """Complete design document for an employee, produced by the Architect."""

    id: UUID = Field(default_factory=uuid4)
    requirements_id: UUID
    org_id: UUID
    employee_type: EmployeeArchetype = EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
    employee_name: str
    components: list[SelectedComponent] = Field(default_factory=list)
    custom_code_specs: list[CustomCodeSpec] = Field(default_factory=list)
    workflow_id: str = "legal_intake"
    tool_permissions: list[str] = Field(default_factory=list)
    identity_layers: IdentityLayerInputs = Field(default_factory=IdentityLayerInputs)
    workflow_description: str = Field("")
    autonomy_profile: dict[str, object] = Field(
        default_factory=dict,
        description="Risk thresholds, approval gates, escalation rules",
    )
    monitoring_policy: MonitoringPolicy = Field(default_factory=MonitoringPolicy)
    deployment_spec: DeploymentSpec = Field(default_factory=DeploymentSpec)
    ui_profile: UIProfile = Field(default_factory=UIProfile)
    estimated_cost_per_task_usd: float | None = None
    architect_reasoning: str = Field("")
    created_at: datetime = Field(default_factory=datetime.utcnow)
