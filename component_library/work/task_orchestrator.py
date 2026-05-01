"""Task orchestration for multi-step employee work."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register


class TaskOrchestrationInput(BaseModel):
    task_type: str
    objective: str
    required_inputs: list[str] = Field(default_factory=list)
    available_inputs: list[str] = Field(default_factory=list)
    risk_tier: str = "medium"


class TaskStep(BaseModel):
    name: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class TaskOrchestrationPlan(BaseModel):
    objective: str
    status: str
    blockers: list[str] = Field(default_factory=list)
    steps: list[TaskStep] = Field(default_factory=list)


@register("task_orchestrator")
class TaskOrchestrator(WorkCapability):
    """Builds dependency-aware plans for employee work."""

    component_id = "task_orchestrator"
    version = "1.0.0"
    config_schema = {
        "approval_risk_tiers": {"type": "list", "required": False, "description": "Risk tiers that require final approval.", "default": ["high", "critical"]},
    }

    async def initialize(self, config: dict[str, Any]) -> None:
        self._approval_risk_tiers = {str(item).lower() for item in config.get("approval_risk_tiers", ["high", "critical"])}

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, TaskOrchestrationInput):
            raise TypeError("TaskOrchestrator expects TaskOrchestrationInput")
        available = {item.lower() for item in input_data.available_inputs}
        blockers = [item for item in input_data.required_inputs if available and item.lower() not in available]
        approval_required = input_data.risk_tier.lower() in self._approval_risk_tiers
        steps = [
            TaskStep(name="collect_inputs", description="Collect required source data and context."),
            TaskStep(name="validate_inputs", description="Validate completeness, freshness, and control totals.", depends_on=["collect_inputs"]),
            TaskStep(name="perform_work", description=f"Execute {input_data.task_type} work product.", depends_on=["validate_inputs"]),
            TaskStep(name="bind_evidence", description="Attach sources, calculations, assumptions, and audit references.", depends_on=["perform_work"]),
            TaskStep(name="quality_review", description="Check evidence, policy, numbers, and output completeness.", depends_on=["bind_evidence"]),
            TaskStep(
                name="approval_handoff",
                description="Route reviewer decision when policy or risk requires it.",
                depends_on=["quality_review"],
                requires_approval=approval_required,
            ),
        ]
        return TaskOrchestrationPlan(
            objective=input_data.objective,
            status="blocked" if blockers else "ready",
            blockers=blockers,
            steps=steps,
        )
