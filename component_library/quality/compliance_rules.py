"""compliance_rules quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class ComplianceAssessment(BaseModel):
    passed: bool
    flags: list[str]


@register("compliance_rules")
class ComplianceRules(QualityModule):
    component_id = "compliance_rules"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._restricted_terms = list(config.get("restricted_terms", []))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_compliance_rules.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        text = str(input_data.get("text", "")) if isinstance(input_data, dict) else str(input_data)
        lowered = text.lower()
        flags = [term for term in self._restricted_terms if term.lower() in lowered]
        return ComplianceAssessment(passed=not flags, flags=flags)
