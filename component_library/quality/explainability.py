"""explainability quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class Explanation(BaseModel):
    summary: str


@register("explainability")
class Explainability(QualityModule):
    component_id = "explainability"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._prefix = str(config.get("prefix", "Decision rationale"))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_explainability.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        text = str(input_data.get("text", "")) if isinstance(input_data, dict) else str(input_data)
        return Explanation(summary=f"{self._prefix}: {text[:240]}")
