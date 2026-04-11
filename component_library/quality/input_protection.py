"""input_protection quality and governance component."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from component_library.work.schemas import InputProtectionResult


@register("input_protection")
class InputProtection(QualityModule):
    component_id = "input_protection"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.get(
                "patterns",
                [
                    r"ignore previous instructions",
                    r"you are now",
                    r"disregard prior",
                    r"new instructions:",
                    r"system:",
                    r"<system>",
                    r"</system>",
                ],
            )
        ]

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_input_protection.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        if isinstance(input_data, str):
            return self.protect(input_data)
        raise TypeError("InputProtection expects a string")

    def protect(self, text: str) -> InputProtectionResult:
        flags: list[str] = []
        sanitized = text
        for pattern in self._patterns:
            if pattern.search(text):
                flags.append(pattern.pattern)
                sanitized = pattern.sub("[filtered]", sanitized)
        risk_score = min(1.0, round(len(flags) * 0.25, 2))
        return InputProtectionResult(
            is_safe=not flags,
            risk_score=risk_score,
            flags=flags,
            sanitized_input=sanitized,
        )
