"""Generic quality review before employee outputs are delivered."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class QualityReviewInput(BaseModel):
    output_text: str
    required_terms: list[str] = Field(default_factory=list)
    expected_numbers: list[float] = Field(default_factory=list)
    policy_decision: str = "autonomous"
    evidence_complete: bool = True


class QualityReviewResult(BaseModel):
    passed: bool
    score: float
    missing_terms: list[str] = Field(default_factory=list)
    numeric_checks_passed: bool = True
    flags: list[str] = Field(default_factory=list)


@register("quality_review_engine")
class QualityReviewEngine(QualityModule):
    """Checks required terms, expected numbers, evidence completeness, and policy boundaries."""

    component_id = "quality_review_engine"
    version = "1.0.0"
    config_schema = {
        "minimum_score": {"type": "float", "required": False, "description": "Minimum quality score to pass.", "default": 0.8},
    }

    async def initialize(self, config: dict[str, Any]) -> None:
        self._minimum_score = float(config.get("minimum_score", 0.8))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        payload = input_data if isinstance(input_data, QualityReviewInput) else QualityReviewInput.model_validate(input_data)
        normalized = " ".join(payload.output_text.lower().replace(",", "").split())
        missing_terms = [term for term in payload.required_terms if term.lower() not in normalized]
        numbers = [float(item.replace(",", "")) for item in re.findall(r"-?\d[\d,]*(?:\.\d+)?", payload.output_text)]
        numeric_passed = all(any(abs(number - expected) <= 0.01 for number in numbers) for expected in payload.expected_numbers)
        flags: list[str] = []
        if payload.policy_decision == "requires_approval":
            flags.append("approval required")
        if payload.policy_decision == "forbidden":
            flags.append("forbidden action")
        if not payload.evidence_complete:
            flags.append("evidence incomplete")
        passed_checks = sum([not missing_terms, numeric_passed, payload.evidence_complete, payload.policy_decision != "forbidden"])
        score = passed_checks / 4
        return QualityReviewResult(
            passed=score >= self._minimum_score and not flags and not missing_terms,
            score=round(score, 3),
            missing_terms=missing_terms,
            numeric_checks_passed=numeric_passed,
            flags=flags,
        )
