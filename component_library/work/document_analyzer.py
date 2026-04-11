"""document_analyzer work capability component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import AnalysisInput, DocumentAnalyzerOutput, LegalIntakeExtraction


@register("document_analyzer")
class DocumentAnalyzer(WorkCapability):
    component_id = "document_analyzer"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._practice_areas = config.get(
            "practice_areas",
            ["personal injury", "employment", "commercial dispute", "real estate"],
        )

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_document_analyzer.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, AnalysisInput):
            return self.analyze(input_data.extraction)
        raise TypeError("DocumentAnalyzer expects AnalysisInput")

    def analyze(self, extraction: LegalIntakeExtraction) -> DocumentAnalyzerOutput:
        risk_flags: list[str] = []
        recommended_actions: list[str] = []
        key_findings: list[str] = []

        if extraction.matter_type:
            key_findings.append(f"Matter type appears to be {extraction.matter_type}.")
        if extraction.estimated_value:
            key_findings.append(f"Reported value/damages: {extraction.estimated_value}.")
        if extraction.opposing_party:
            key_findings.append(f"Potential conflict party identified: {extraction.opposing_party}.")
        if extraction.urgency in {"high", "urgent"}:
            key_findings.append(f"Urgency level is {extraction.urgency}.")

        practice_match = extraction.matter_type in self._practice_areas
        if not extraction.matter_type:
            risk_flags.append("Matter type is unclear.")
        elif not practice_match and extraction.matter_type != "parking ticket":
            risk_flags.append("Matter may fall outside configured practice areas.")

        if extraction.extraction_confidence < 0.65:
            risk_flags.append("Insufficient intake detail for confident qualification.")

        if "30 days" in extraction.raw_summary.lower() or extraction.urgency == "urgent":
            risk_flags.append("Possible statute of limitations or urgent filing deadline.")

        if extraction.matter_type == "parking ticket":
            decision = "not_qualified"
            recommended_actions.extend(
                ["Send decline response.", "Recommend local traffic or municipal counsel if appropriate."]
            )
        elif extraction.extraction_confidence < 0.55 or not extraction.matter_type:
            decision = "needs_review"
            recommended_actions.extend(
                ["Request more factual detail from the prospect.", "Route to an attorney for judgment."]
            )
        elif practice_match or extraction.matter_type in {"personal injury", "commercial dispute"}:
            decision = "qualified"
            recommended_actions.extend(
                ["Schedule consultation.", "Run formal conflict check.", "Request supporting records."]
            )
        else:
            decision = "not_qualified"
            recommended_actions.append("Send polite decline and redirect if possible.")

        summary = self._build_summary(extraction, decision, risk_flags)
        reasoning = self._build_reasoning(extraction, decision, practice_match, risk_flags)
        confidence = round(min(0.95, max(0.3, extraction.extraction_confidence + 0.08)), 2)

        return DocumentAnalyzerOutput(
            summary=summary,
            key_findings=key_findings[:5] or ["Intake information was limited."],
            risk_flags=risk_flags,
            recommended_actions=recommended_actions[:4],
            qualification_decision=decision,
            qualification_reasoning=reasoning,
            confidence=confidence,
        )

    def _build_summary(
        self,
        extraction: LegalIntakeExtraction,
        decision: str,
        risk_flags: list[str],
    ) -> str:
        risk_text = " ".join(risk_flags[:2]) if risk_flags else "No major intake red flags detected."
        return (
            f"This inquiry appears to be a {decision.replace('_', ' ')} matter for the firm. "
            f"{risk_text}"
        )

    def _build_reasoning(
        self,
        extraction: LegalIntakeExtraction,
        decision: str,
        practice_match: bool,
        risk_flags: list[str],
    ) -> str:
        if decision == "qualified":
            return (
                f"The matter aligns with the firm's practice profile and includes enough facts "
                f"to support follow-up. Practice-area match: {practice_match or extraction.matter_type in {'personal injury', 'commercial dispute'}}."
            )
        if decision == "needs_review":
            return (
                "The intake suggests a potentially viable legal issue, but the submission omits key facts "
                "or introduces uncertainty that requires attorney judgment."
            )
        return (
            "The inquiry is outside the current firm focus or too low-value for standard intake handling. "
            + (" ".join(risk_flags[:2]) if risk_flags else "")
        )
