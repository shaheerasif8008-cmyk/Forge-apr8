"""verification_layer quality and governance component."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from component_library.work.schemas import VerificationInput, VerificationResult


@register("verification_layer")
class VerificationLayer(QualityModule):
    component_id = "verification_layer"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_verification_layer.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        if isinstance(input_data, VerificationInput):
            return self.verify(input_data)
        raise TypeError("VerificationLayer expects VerificationInput")

    def verify(self, input_data: VerificationInput) -> VerificationResult:
        brief = input_data.brief
        flags: list[str] = []
        extraction = brief.client_info
        if not extraction.client_name:
            flags.append("Missing client_name")
        if not extraction.matter_type:
            flags.append("Missing matter_type")
        if not brief.analysis.qualification_decision:
            flags.append("Missing qualification_decision")
        if extraction.client_email and not re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", extraction.client_email):
            flags.append("Invalid email format")
        if extraction.client_phone and not re.search(r"\d{3}.*\d{3}.*\d{4}", extraction.client_phone):
            flags.append("Invalid phone format")
        if brief.analysis.qualification_decision == "qualified" and brief.confidence_score < 0.3:
            flags.append("Qualified brief has implausibly low confidence")
        return VerificationResult(
            is_valid=not flags,
            flags=flags,
            normalized_fields={
                "client_name": extraction.client_name.strip(),
                "matter_type": extraction.matter_type.strip(),
                "qualification_decision": brief.analysis.qualification_decision,
            },
        )
