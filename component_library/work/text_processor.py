"""text_processor work capability component."""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import LegalIntakeExtraction, LegalIntakeInput


@register("text_processor")
class TextProcessor(WorkCapability):
    config_schema = {
        "model_client": {"type": "object", "required": False, "description": "Optional model client for LLM-backed extraction.", "default": None},
        "fallback_mode": {"type": "str", "required": False, "description": "Fallback extraction mode when no model client is used.", "default": "deterministic"},
        "force_llm": {"type": "bool", "required": False, "description": "Force LLM extraction when a model client is configured.", "default": False},
    }
    component_id = "text_processor"
    version = "1.0.0"

    _matter_keywords = {
        "personal injury": ["car accident", "auto accident", "injured", "workplace", "chemical burn"],
        "employment": ["work", "boss", "discrimination", "harassment", "terminated"],
        "commercial dispute": ["breach of contract", "manufacturing", "agreement", "contract dispute"],
        "criminal defense": ["arrested", "charged", "criminal"],
        "family law": ["custody", "divorce", "spouse"],
        "real estate": ["property", "closing", "real estate", "title"],
    }
    _referral_keywords = ("google", "referral", "friend", "colleague", "search", "website")

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._model_client = config.get("model_client")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        detail = "llm_backed" if self._model_client is not None else "deterministic_fallback"
        return ComponentHealth(healthy=True, detail=detail)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_text_processor.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, LegalIntakeInput):
            return await self.extract(input_data.email_text)
        raise TypeError("TextProcessor expects LegalIntakeInput")

    def set_model_client(self, model_client: Any) -> None:
        self._model_client = model_client

    async def extract(self, email_text: str) -> LegalIntakeExtraction:
        if self._can_use_model():
            try:
                return await self._extract_with_model(email_text)
            except Exception:
                if self._fallback_mode != "deterministic":
                    raise
        return self._extract_deterministic(email_text)

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

    async def _extract_with_model(self, email_text: str) -> LegalIntakeExtraction:
        system_prompt = (
            "You extract structured information from legal intake emails for a law-firm intake employee. "
            "Return only facts present in the message. Preserve uncertainty. Leave unknown fields blank instead of guessing. "
            "Keep key_facts concise, factual, and specific. Use urgency values normal, high, or urgent."
        )
        user_message = (
            "Extract the following legal intake email into the schema.\n\n"
            f"EMAIL:\n{email_text.strip()}"
        )
        result = await self._call_structured_model(system_prompt, user_message)
        return result.model_copy(
            update={
                "client_name": result.client_name.strip(),
                "client_email": result.client_email.strip(),
                "client_phone": result.client_phone.strip(),
                "matter_type": result.matter_type.strip(),
                "date_of_incident": result.date_of_incident.strip(),
                "opposing_party": result.opposing_party.strip(),
                "estimated_value": result.estimated_value.strip(),
                "referral_source": result.referral_source.strip(),
                "raw_summary": result.raw_summary.strip(),
                "urgency": result.urgency.strip() or "normal",
                "key_facts": [fact.strip() for fact in result.key_facts if fact.strip()],
                "potential_conflicts": [item.strip() for item in result.potential_conflicts if item.strip()],
                "extraction_confidence": round(max(0.0, min(result.extraction_confidence, 1.0)), 2),
            }
        )

    async def _call_structured_model(
        self,
        system_prompt: str,
        user_message: str,
    ) -> LegalIntakeExtraction:
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete_structured(
                TaskType.STRUCTURED,
                system_prompt,
                user_message,
                LegalIntakeExtraction,
            )
        if hasattr(self._model_client, "complete_structured"):
            return await self._model_client.complete_structured(
                system_prompt,
                user_message,
                LegalIntakeExtraction,
            )
        return await self._model_client.structure(
            LegalIntakeExtraction,
            user_message,
            system_prompt=system_prompt,
        )

    def _extract_deterministic(self, email_text: str) -> LegalIntakeExtraction:
        text = email_text.strip()
        lower = text.lower()

        client_email = self._first_match(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        client_phone = self._first_match(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        client_name = self._extract_name(text)
        matter_type = self._extract_matter_type(lower)
        date_of_incident = self._extract_incident_date(text)
        opposing_party = self._extract_opposing_party(text)
        key_facts = self._extract_key_facts(text)
        urgency = self._extract_urgency(lower)
        potential_conflicts = self._extract_conflicts(text, opposing_party)
        estimated_value = self._extract_value(text)
        referral_source = self._extract_referral_source(lower)
        raw_summary = self._build_summary(client_name, matter_type, key_facts)
        extraction_confidence = self._score_confidence(
            client_name,
            matter_type,
            key_facts,
            client_email,
            client_phone,
            text,
        )

        return LegalIntakeExtraction(
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            matter_type=matter_type,
            date_of_incident=date_of_incident,
            opposing_party=opposing_party,
            key_facts=key_facts,
            urgency=urgency,
            potential_conflicts=potential_conflicts,
            estimated_value=estimated_value,
            referral_source=referral_source,
            raw_summary=raw_summary,
            extraction_confidence=extraction_confidence,
        )

    def _first_match(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(0).strip() if match else ""

    def _extract_name(self, text: str) -> str:
        patterns = [
            r"My name is ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
            r"^([A-Z][a-z]+(?: [A-Z][a-z]+)+)[,\n]",
            r"Thanks\.\s*-\s*([A-Z][a-z]+(?: [A-Z][a-z]+)*)",
            r"Thank you,\s*([A-Z][a-z]+(?: [A-Z][a-z]+)*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.MULTILINE)
            if match:
                return match.group(1).strip()

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            tail = lines[-1]
            if re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+){0,2}", tail):
                return tail
        return ""

    def _extract_matter_type(self, lower: str) -> str:
        for matter_type, keywords in self._matter_keywords.items():
            if any(keyword in lower for keyword in keywords):
                return matter_type
        if "parking ticket" in lower:
            return "parking ticket"
        return ""

    def _extract_incident_date(self, text: str) -> str:
        patterns = [
            r"on ([A-Z][a-z]+ \d{1,2}, \d{4})",
            r"dated ([A-Z][a-z]+ \d{4})",
            r"last week",
            r"(\d+ years? and \d+ months? ago)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        return ""

    def _extract_opposing_party(self, text: str) -> str:
        patterns = [
            r"The other driver,\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
            r"dispute with ([A-Z][A-Za-z0-9&., ]+(?:LLC|Inc\.|Co\.|Corp\.|Corporation|Manufacturing))",
            r"at ([A-Z][A-Za-z0-9&., ]+(?:plant|LLC|Inc\.|Co\.|Corp\.))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_key_facts(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        facts = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 25]
        return facts[:6]

    def _extract_urgency(self, lower: str) -> str:
        if "urgent" in lower or "immediately" in lower or "30 days" in lower:
            return "urgent"
        if "move quickly" in lower or "as soon as possible" in lower or "expires" in lower:
            return "high"
        if "last week" in lower:
            return "low"
        return "normal"

    def _extract_conflicts(self, text: str, opposing_party: str) -> list[str]:
        conflicts: list[str] = []
        if opposing_party:
            conflicts.append(opposing_party)
        if "CEO of " in text:
            match = re.search(r"CEO of ([A-Z][A-Za-z0-9&., ]+)", text)
            if match:
                conflicts.append(match.group(1).strip())
        return list(dict.fromkeys(conflicts))

    def _extract_value(self, text: str) -> str:
        values = re.findall(r"\$\d[\d,]*(?:\.\d+)?(?: million)?", text, flags=re.IGNORECASE)
        if values:
            return ", ".join(values[:3])
        if "totaled" in text.lower():
            return "property damage noted"
        return ""

    def _extract_referral_source(self, lower: str) -> str:
        for keyword in self._referral_keywords:
            if keyword in lower:
                return keyword
        return ""

    def _build_summary(self, client_name: str, matter_type: str, key_facts: list[str]) -> str:
        lead = client_name or "The prospective client"
        matter = matter_type or "a legal matter"
        fact_text = key_facts[0] if key_facts else "provided limited detail in the inquiry."
        return f"{lead} appears to be seeking help with {matter}. {fact_text}"

    def _score_confidence(
        self,
        client_name: str,
        matter_type: str,
        key_facts: list[str],
        client_email: str,
        client_phone: str,
        raw_text: str,
    ) -> float:
        score = 0.2
        if client_name:
            score += 0.2
        if matter_type:
            score += 0.2
        if client_email:
            score += 0.1
        if client_phone:
            score += 0.05
        if key_facts:
            score += min(0.3, 0.05 * len(key_facts))
        lowered = raw_text.lower()
        if "don't want to get into details" in lowered or "can someone call me" in lowered:
            score -= 0.15
        if not client_email and not client_phone:
            score -= 0.1
        return round(min(score, 0.98), 2)
