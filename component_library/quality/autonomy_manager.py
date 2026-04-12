"""autonomy_manager quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class AutonomyDecision(BaseModel):
    confidence_score: float
    requires_approval: bool


@register("autonomy_manager")
class AutonomyManager(QualityModule):
    component_id = "autonomy_manager"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._approval_threshold = float(config.get("approval_threshold", 0.7))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_autonomy_manager.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        score = float(input_data.get("confidence_score", 0.0)) if isinstance(input_data, dict) else 0.0
        return AutonomyDecision(confidence_score=score, requires_approval=score < self._approval_threshold)
