"""explainability quality and governance component."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register


@register("explainability")
class Uexplainability(BaseComponent):
    component_id = "explainability"
    version = "1.0.0"
    category = "quality"

    async def initialize(self, config: dict[str, Any]) -> None:
        pass

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_explainability.py"]
