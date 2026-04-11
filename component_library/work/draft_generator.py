"""draft_generator work capability component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import DraftInput, IntakeBrief


@register("draft_generator")
class DraftGenerator(WorkCapability):
    component_id = "draft_generator"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._default_attorney = config.get("default_attorney", "Review Attorney")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_draft_generator.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, DraftInput):
            return self.generate(input_data)
        raise TypeError("DraftGenerator expects DraftInput")

    def generate(self, input_data: DraftInput) -> IntakeBrief:
        extraction = input_data.extraction
        analysis = input_data.analysis
        confidence_report = input_data.confidence_report
        executive_summary = (
            f"{extraction.client_name or 'Prospect'} submitted a {extraction.matter_type or 'legal'} inquiry. "
            f"Recommendation: {analysis.qualification_decision.replace('_', ' ')}. "
            f"{analysis.qualification_reasoning}"
        )
        return IntakeBrief(
            client_info=extraction,
            analysis=analysis,
            confidence_score=confidence_report.overall_score,
            executive_summary=executive_summary,
            recommended_attorney=self._default_attorney,
            recommended_practice_area=extraction.matter_type,
            next_steps=analysis.recommended_actions,
            flags=analysis.risk_flags,
        )
