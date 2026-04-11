"""confidence_scorer quality and governance component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from component_library.work.schemas import ConfidenceInput, ConfidenceReport


@register("confidence_scorer")
class ConfidenceScorer(QualityModule):
    component_id = "confidence_scorer"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._router = config.get("router")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_confidence_scorer.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        if isinstance(input_data, ConfidenceInput):
            return self.score(input_data)
        raise TypeError("ConfidenceScorer expects ConfidenceInput")

    def score(self, input_data: ConfidenceInput) -> ConfidenceReport:
        extraction = input_data.extraction
        analysis = input_data.analysis
        completeness = sum(
            1 for value in [extraction.client_name, extraction.matter_type, extraction.client_email, extraction.key_facts] if value
        ) / 4
        consistency = 1.0
        flags: list[str] = []
        if analysis.qualification_decision == "qualified" and extraction.extraction_confidence < 0.45:
            consistency -= 0.35
            flags.append("Qualification decision is stronger than the extracted detail supports.")
        if analysis.qualification_decision == "needs_review":
            consistency -= 0.1
        structural_score = round(max(0.0, min(1.0, (completeness * 0.7) + (consistency * 0.3))), 2)
        llm_self_assessment = round(max(0.0, min(1.0, (analysis.confidence + extraction.extraction_confidence) / 2)), 2)
        overall = round((structural_score * 0.55) + (llm_self_assessment * 0.45), 2)
        if overall >= 0.85:
            recommendation = "proceed"
        elif overall >= 0.4:
            recommendation = "review"
        else:
            recommendation = "escalate"
        if completeness < 0.5:
            flags.append("Several required intake fields are incomplete.")
        return ConfidenceReport(
            overall_score=overall,
            llm_self_assessment=llm_self_assessment,
            structural_score=structural_score,
            dimension_scores={
                "completeness": round(completeness, 2),
                "consistency": round(consistency, 2),
                "analysis_confidence": analysis.confidence,
            },
            flags=flags,
            recommendation=recommendation,
        )
