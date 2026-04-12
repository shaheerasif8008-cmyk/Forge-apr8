"""workflow_executor work capability component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import ExecutiveAssistantInput, ExecutiveAssistantPlan


@register("workflow_executor")
class WorkflowExecutor(WorkCapability):
    component_id = "workflow_executor"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._auto_actions = config.get(
            "auto_actions",
            ["triage request", "draft response", "prepare follow-up"],
        )

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_workflow_executor.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ExecutiveAssistantInput):
            raise TypeError("WorkflowExecutor expects ExecutiveAssistantInput")
        return self.plan(input_data.request_text)

    def plan(self, request_text: str) -> ExecutiveAssistantPlan:
        lowered = request_text.lower()
        requested_actions = list(self._auto_actions)
        if "schedule" in lowered or "meeting" in lowered:
            requested_actions.insert(0, "coordinate calendar")
        if "client" in lowered or "customer" in lowered:
            requested_actions.append("update crm record")
        stakeholders = []
        if "sarah" in lowered:
            stakeholders.append("Sarah")
        if "finance" in lowered:
            stakeholders.append("Finance")
        requires_approval = any(keyword in lowered for keyword in ("approve", "sign", "send to all"))
        return ExecutiveAssistantPlan(
            summary=request_text.strip()[:240],
            requested_actions=requested_actions[:5],
            stakeholders=stakeholders,
            meeting_topics=["meeting coordination"] if "meeting" in lowered else [],
            deadlines=["high priority"] if "asap" in lowered or "urgent" in lowered else [],
            requires_approval=requires_approval,
            rationale="Derived from request intent, timing cues, and stakeholder mentions.",
        )
