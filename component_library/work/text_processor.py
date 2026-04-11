"""text_processor work capability component."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import LegalIntakeExtraction, LegalIntakeInput


@register("text_processor")
class TextProcessor(WorkCapability):
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

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_text_processor.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if isinstance(input_data, LegalIntakeInput):
            return self.extract(input_data.email_text)
        raise TypeError("TextProcessor expects LegalIntakeInput")

    def extract(self, email_text: str) -> LegalIntakeExtraction:
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
        extraction_confidence = self._score_confidence(client_name, matter_type, key_facts, client_email)

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
    ) -> float:
        score = 0.2
        if client_name:
            score += 0.2
        if matter_type:
            score += 0.2
        if client_email:
            score += 0.1
        if key_facts:
            score += min(0.3, 0.05 * len(key_facts))
        return round(min(score, 0.98), 2)
