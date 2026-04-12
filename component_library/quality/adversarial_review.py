"""adversarial_review quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class AdversarialReviewResult(BaseModel):
    approved: bool
    concerns: list[str]


@register("adversarial_review")
class AdversarialReview(QualityModule):
    component_id = "adversarial_review"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._keywords = list(config.get("concern_keywords", ["wire transfer", "delete data", "legal advice"]))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_adversarial_review.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        text = str(input_data.get("text", "")) if isinstance(input_data, dict) else str(input_data)
        lowered = text.lower()
        concerns = [keyword for keyword in self._keywords if keyword in lowered]
        return AdversarialReviewResult(approved=not concerns, concerns=concerns)
