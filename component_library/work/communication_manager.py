"""communication_manager work capability component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import ExecutiveAssistantPlan, ExecutiveAssistantResult


@register("communication_manager")
class CommunicationManager(WorkCapability):
    config_schema = {
        "voice": {"type": "str", "required": False, "description": "Default communication voice/tone.", "default": "clear and concise"},
        "signature": {"type": "str", "required": False, "description": "Signature/name used in outgoing communications.", "default": "Forge Employee"},
    }
    component_id = "communication_manager"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._voice = config.get("voice", "clear and concise")
        self._signature = config.get("signature", "Forge Employee")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_communication_manager.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ExecutiveAssistantPlan):
            raise TypeError("CommunicationManager expects ExecutiveAssistantPlan")
        return self.compose(input_data)

    def compose(self, plan: ExecutiveAssistantPlan) -> ExecutiveAssistantResult:
        actions = plan.requested_actions or ["Acknowledge request", "Prepare next step summary"]
        if plan.is_novel_situation:
            drafted_response = (
                "I haven't handled this exact situation before. "
                "Here are three approaches: "
                + "; ".join(
                    f"[{option['key']}] {option['label']}: {option['description']}"
                    for option in plan.novel_options
                )
                + f" Recommended: {plan.recommended_option}."
                + f" - {self._signature}"
            )
            return ExecutiveAssistantResult(
                title="Guidance Needed",
                summary=plan.guidance_request or plan.summary,
                drafted_response=drafted_response,
                action_items=["Review options", "Choose an approach", "Confirm any constraints"],
                confidence_score=0.46,
                novel_options=plan.novel_options,
                recommended_option=plan.recommended_option,
                needs_guidance=True,
            )
        drafted_response = (
            f"I've reviewed the request. {plan.summary} "
            f"My next steps are: {', '.join(actions[:3])}. "
            f"Tone: {self._voice}. "
            f"- {self._signature}"
        )
        return ExecutiveAssistantResult(
            title="Executive Assistant Update",
            summary=plan.summary,
            drafted_response=drafted_response,
            action_items=actions[:5],
            confidence_score=0.82 if not plan.requires_approval else 0.68,
            novel_options=plan.novel_options,
            recommended_option=plan.recommended_option,
            needs_guidance=False,
        )
