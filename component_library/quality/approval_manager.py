"""approval_manager quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class ApprovalAssessment(BaseModel):
    required: bool
    reason: str = ""


@register("approval_manager")
class ApprovalManager(QualityModule):
    config_schema = {
        "default_required": {"type": "bool", "required": False, "description": "Default approval requirement when input does not specify one.", "default": False},
    }
    component_id = "approval_manager"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._default_required = bool(config.get("default_required", False))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_approval_manager.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        if isinstance(input_data, dict):
            required = bool(input_data.get("requires_approval", self._default_required))
            reason = str(input_data.get("reason", ""))
        else:
            required = self._default_required
            reason = ""
        return ApprovalAssessment(required=required, reason=reason)
