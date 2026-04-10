"""Employee blueprint — output of the Architect stage."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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


class EmployeeBlueprint(BaseModel):
    """Complete design document for an employee, produced by the Architect."""

    id: UUID = Field(default_factory=uuid4)
    requirements_id: UUID
    org_id: UUID
    employee_name: str
    components: list[SelectedComponent] = Field(default_factory=list)
    custom_code_specs: list[CustomCodeSpec] = Field(default_factory=list)
    workflow_description: str = Field("")
    autonomy_profile: dict[str, object] = Field(
        default_factory=dict,
        description="Risk thresholds, approval gates, escalation rules",
    )
    estimated_cost_per_task_usd: float | None = None
    architect_reasoning: str = Field("")
    created_at: datetime = Field(default_factory=datetime.utcnow)
