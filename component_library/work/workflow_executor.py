"""workflow_executor work capability component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import ExecutiveAssistantInput, ExecutiveAssistantPlan


@register("workflow_executor")
class WorkflowExecutor(WorkCapability):
    config_schema = {
        "auto_actions": {"type": "list", "required": False, "description": "Action names the executor may run without approval.", "default": ["analyze", "draft", "classify"]},
    }
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
        recognized_intent = False
        if "schedule" in lowered or "meeting" in lowered:
            requested_actions.insert(0, "coordinate calendar")
            recognized_intent = True
        if "client" in lowered or "customer" in lowered:
            requested_actions.append("update crm record")
            recognized_intent = True
        stakeholders = []
        if "sarah" in lowered:
            stakeholders.append("Sarah")
        if "finance" in lowered:
            stakeholders.append("Finance")
        if "follow-up" in lowered or "follow up" in lowered or "respond" in lowered or "reply" in lowered:
            recognized_intent = True
        requires_approval = any(keyword in lowered for keyword in ("approve", "sign", "send to all"))
        novel_trigger = self._novel_trigger(lowered, recognized_intent)
        is_novel_situation = novel_trigger != ""
        novel_options = self._novel_options(request_text) if is_novel_situation else []
        return ExecutiveAssistantPlan(
            summary=request_text.strip()[:240],
            requested_actions=requested_actions[:5],
            stakeholders=stakeholders,
            meeting_topics=["meeting coordination"] if "meeting" in lowered else [],
            deadlines=["high priority"] if "asap" in lowered or "urgent" in lowered else [],
            requires_approval=requires_approval or is_novel_situation,
            rationale="Derived from request intent, timing cues, and stakeholder mentions.",
            is_novel_situation=is_novel_situation,
            novel_options=novel_options,
            recommended_option=novel_options[0]["key"] if novel_options else "",
            guidance_request=(
                "I haven't handled this exact situation before. Here are three approaches with tradeoffs."
                if is_novel_situation
                else ""
            ),
            novel_trigger=novel_trigger,
        )

    def _novel_trigger(self, lowered: str, recognized_intent: bool) -> str:
        explicit_cues = (
            "never handled",
            "never seen",
            "first time",
            "novel",
            "untested",
            "creative option",
            "outside our normal process",
            "outside your domain",
            "something new",
        )
        for cue in explicit_cues:
            if cue in lowered:
                return cue
        if not recognized_intent and len(lowered.split()) >= 8:
            return "unrecognized_request_pattern"
        return ""

    def _novel_options(self, request_text: str) -> list[dict[str, str]]:
        summary = request_text.strip()[:120]
        return [
            {
                "key": "A",
                "label": "Safest",
                "description": f"Pause external action, gather missing facts, and confirm the right process for: {summary}",
            },
            {
                "key": "B",
                "label": "Faster",
                "description": f"Take the most likely next step for: {summary}, but keep the action reversible and reviewable.",
            },
            {
                "key": "C",
                "label": "Creative",
                "description": f"Try a new approach for: {summary}, mark it as untested, and escalate results immediately.",
            },
        ]
