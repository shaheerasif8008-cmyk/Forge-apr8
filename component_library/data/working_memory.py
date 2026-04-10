"""working_memory data source component."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register


@register("working_memory")
class UworkingUmemory(BaseComponent):
    component_id = "working_memory"
    version = "1.0.0"
    category = "data"

    async def initialize(self, config: dict[str, Any]) -> None:
        pass

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_working_memory.py"]
