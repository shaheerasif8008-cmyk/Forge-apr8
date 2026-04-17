"""draft_generator work capability component."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import DraftInput, IntakeBrief


@register("draft_generator")
class DraftGenerator(WorkCapability):
    component_id = "draft_generator"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._default_attorney = config.get("default_attorney", "Review Attorney")
        self._model_client = config.get("model_client")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        detail = "llm_backed" if self._model_client is not None else "deterministic_fallback"
        return ComponentHealth(healthy=True, detail=detail)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_draft_generator.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, DraftInput):
            return await self.generate(input_data)
        raise TypeError("DraftGenerator expects DraftInput")

    def set_model_client(self, model_client: Any) -> None:
        self._model_client = model_client

    async def generate(self, input_data: DraftInput) -> IntakeBrief:
        if self._can_use_model():
            try:
                return await self._generate_with_model(input_data)
            except Exception:
                if self._fallback_mode != "deterministic":
                    raise
        return self._generate_deterministic(input_data)

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

    async def _generate_with_model(self, input_data: DraftInput) -> IntakeBrief:
        system_prompt = (
            "You draft compact legal-intake briefs for attorneys. Use the provided extraction, analysis, and confidence only. "
            "Do not add new facts. Preserve the nested client_info and analysis exactly unless formatting cleanup is required. "
            "Write a concise executive_summary, next_steps, flags, recommended_practice_area, and recommended_attorney."
        )
        user_message = (
            "Produce the structured intake brief.\n\n"
            f"DEFAULT ATTORNEY: {self._default_attorney}\n\n"
            f"INPUT JSON:\n{json.dumps(input_data.model_dump(mode='json'), indent=2)}"
        )
        result = await self._call_structured_model(system_prompt, user_message)
        return result.model_copy(
            update={
                "client_info": input_data.extraction,
                "analysis": input_data.analysis,
                "confidence_score": input_data.confidence_report.overall_score,
                "recommended_attorney": result.recommended_attorney.strip() or self._default_attorney,
                "recommended_practice_area": result.recommended_practice_area.strip() or input_data.extraction.matter_type,
                "executive_summary": result.executive_summary.strip(),
                "next_steps": [item.strip() for item in result.next_steps if item.strip()],
                "flags": [item.strip() for item in result.flags if item.strip()],
            }
        )

    async def _call_structured_model(
        self,
        system_prompt: str,
        user_message: str,
    ) -> IntakeBrief:
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete_structured(
                TaskType.STRUCTURED,
                system_prompt,
                user_message,
                IntakeBrief,
            )
        if hasattr(self._model_client, "complete_structured"):
            return await self._model_client.complete_structured(
                system_prompt,
                user_message,
                IntakeBrief,
            )
        return await self._model_client.structure(
            IntakeBrief,
            user_message,
            system_prompt=system_prompt,
        )

    def _generate_deterministic(self, input_data: DraftInput) -> IntakeBrief:
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
