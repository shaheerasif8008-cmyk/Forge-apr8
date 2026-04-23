"""document_analyzer work capability component."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import (
    AnalysisInput,
    DocumentAnalyzerOutput,
    LegalIntakeExtraction,
)


@register("document_analyzer")
class DocumentAnalyzer(WorkCapability):
    config_schema = {
        "practice_areas": {"type": "list", "required": False, "description": "Practice areas or domains used for qualification analysis.", "default": []},
        "model_client": {"type": "object", "required": False, "description": "Optional model client for LLM-backed analysis.", "default": None},
        "fallback_mode": {"type": "str", "required": False, "description": "Fallback analysis mode when no model client is used.", "default": "deterministic"},
        "force_llm": {"type": "bool", "required": False, "description": "Force LLM analysis when a model client is configured.", "default": False},
    }
    component_id = "document_analyzer"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._practice_areas = config.get(
            "practice_areas",
            ["personal injury", "employment", "commercial dispute", "real estate"],
        )
        self._model_client = config.get("model_client")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        detail = "llm_backed" if self._model_client is not None else "deterministic_fallback"
        return ComponentHealth(healthy=True, detail=detail)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_document_analyzer.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, AnalysisInput):
            return await self.analyze(input_data.extraction)
        raise TypeError("DocumentAnalyzer expects AnalysisInput")

    def set_model_client(self, model_client: Any) -> None:
        self._model_client = model_client

    async def analyze(self, extraction: LegalIntakeExtraction) -> DocumentAnalyzerOutput:
        if self._can_use_model():
            try:
                return await self._analyze_with_model(extraction)
            except Exception:
                if self._fallback_mode != "deterministic":
                    raise
        return self._analyze_deterministic(extraction)

    def _can_use_model(self) -> bool:
        if self._model_client is None:
            return False
        if self._config.get("force_llm"):
            return True
        client_id = getattr(self._model_client, "component_id", "")
        if client_id == "litellm_router":
            return any(
                os.getenv(name)
                for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
            )
        if client_id == "anthropic_provider":
            return bool(getattr(self._model_client, "_api_key", None) or os.getenv("ANTHROPIC_API_KEY"))
        return True

    async def _analyze_with_model(
        self,
        extraction: LegalIntakeExtraction,
    ) -> DocumentAnalyzerOutput:
        system_prompt = (
            "You are a legal-intake qualification analyst. Reason only from the extracted intake facts provided. "
            "Do not invent missing details. Choose qualification_decision from qualified, needs_review, or not_qualified. "
            "Identify risk_flags, recommended_actions, a concise summary, and clear qualification_reasoning."
        )
        user_message = (
            "Analyze this intake against the firm's practice areas and produce the structured qualification output.\n\n"
            f"PRACTICE AREAS: {', '.join(self._practice_areas)}\n\n"
            f"EXTRACTION JSON:\n{json.dumps(extraction.model_dump(mode='json'), indent=2)}"
        )
        result = await self._call_structured_model(system_prompt, user_message)
        return result.model_copy(
            update={
                "summary": result.summary.strip(),
                "key_findings": [item.strip() for item in result.key_findings if item.strip()],
                "risk_flags": [item.strip() for item in result.risk_flags if item.strip()],
                "recommended_actions": [item.strip() for item in result.recommended_actions if item.strip()],
                "qualification_decision": result.qualification_decision.strip(),
                "qualification_reasoning": result.qualification_reasoning.strip(),
                "confidence": round(max(0.0, min(result.confidence, 1.0)), 2),
            }
        )

    async def _call_structured_model(
        self,
        system_prompt: str,
        user_message: str,
    ) -> DocumentAnalyzerOutput:
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete_structured(
                TaskType.STRUCTURED,
                system_prompt,
                user_message,
                DocumentAnalyzerOutput,
            )
        if hasattr(self._model_client, "complete_structured"):
            return await self._model_client.complete_structured(
                system_prompt,
                user_message,
                DocumentAnalyzerOutput,
            )
        return await self._model_client.structure(
            DocumentAnalyzerOutput,
            user_message,
            system_prompt=system_prompt,
        )

    def _analyze_deterministic(self, extraction: LegalIntakeExtraction) -> DocumentAnalyzerOutput:
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
        if not extraction.client_email and not extraction.client_phone:
            risk_flags.append("Missing direct contact information for immediate follow-up.")
        if "don't want to get into details" in " ".join(extraction.key_facts).lower():
            risk_flags.append("Prospect withheld key facts over email.")

        if "30 days" in extraction.raw_summary.lower() or extraction.urgency == "urgent":
            risk_flags.append("Possible statute of limitations or urgent filing deadline.")

        if extraction.matter_type == "parking ticket":
            decision = "not_qualified"
            recommended_actions.extend(
                ["Send decline response.", "Recommend local traffic or municipal counsel if appropriate."]
            )
        elif (
            extraction.extraction_confidence < 0.72
            or not extraction.matter_type
            or (not extraction.client_email and not extraction.client_phone)
        ):
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
