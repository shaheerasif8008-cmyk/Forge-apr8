"""input_protection quality and governance component."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from component_library.work.schemas import InputProtectionResult

logger = structlog.get_logger(__name__)

_DEFAULT_VALIDATORS = [
    {"id": "prompt_injection", "enabled": True, "severity": 0.5},
    {"id": "pii", "enabled": True, "severity": 0.1, "blocking": False, "redact": False},
    {"id": "toxicity", "enabled": True, "severity": 0.25},
]


@register("input_protection")
class InputProtection(QualityModule):
    component_id = "input_protection"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._validator_specs = self._load_validator_specs(config)
        self._prompt_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.get(
                "prompt_injection_patterns",
                [
                    r"ignore previous instructions",
                    r"you are now",
                    r"disregard prior",
                    r"new instructions:",
                    r"system:",
                    r"<system>",
                    r"</system>",
                ],
            )
        ]
        self._pii_patterns = {
            "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
            "phone": re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
        }
        self._toxic_terms = [term.lower() for term in config.get("toxic_terms", ["idiot", "stupid", "hate you"])]

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True, detail=f"validators={len(self._validator_specs)}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_input_protection.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        if isinstance(input_data, str):
            return self.protect(input_data)
        raise TypeError("InputProtection expects a string")

    def protect(self, text: str) -> InputProtectionResult:
        sanitized = text
        flags: list[str] = []
        violations: list[dict[str, Any]] = []
        risk_score = 0.0
        blocking_hits = 0

        for validator in self._validator_specs:
            if not validator.get("enabled", True):
                continue
            validator_id = str(validator["id"])
            severity = float(validator.get("severity", 0.25))
            blocking = bool(validator.get("blocking", validator_id != "pii"))
            handler = getattr(self, f"_run_{validator_id}_validator", None)
            if handler is None:
                logger.warning("input_protection_unknown_validator", validator=validator_id)
                continue
            result = handler(sanitized, validator)
            if not result["matched"]:
                continue
            risk_score += severity
            if blocking:
                blocking_hits += 1
            flags.append(validator_id)
            violations.append(
                {
                    "validator": validator_id,
                    "detail": result["detail"],
                    "severity": severity,
                    "blocking": blocking,
                }
            )
            sanitized = result["sanitized"]

        return InputProtectionResult(
            is_safe=blocking_hits == 0,
            risk_score=round(min(1.0, risk_score), 2),
            flags=flags,
            violations=violations,
            sanitized_input=sanitized,
        )

    def _load_validator_specs(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        if "validators" in config:
            return [dict(item) for item in config["validators"]]
        config_path = config.get("validators_path")
        if config_path:
            payload = yaml.safe_load(Path(str(config_path)).read_text(encoding="utf-8")) or {}
            return [dict(item) for item in payload.get("validators", [])]
        return [dict(item) for item in _DEFAULT_VALIDATORS]

    def _run_prompt_injection_validator(self, text: str, validator: dict[str, Any]) -> dict[str, Any]:
        sanitized = text
        matches: list[str] = []
        for pattern in self._prompt_patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)
                sanitized = pattern.sub("[filtered]", sanitized)
        return {
            "matched": bool(matches),
            "detail": ", ".join(matches),
            "sanitized": sanitized,
        }

    def _run_pii_validator(self, text: str, validator: dict[str, Any]) -> dict[str, Any]:
        sanitized = text
        matches: list[str] = []
        redact = bool(validator.get("redact", False))
        for pii_type, pattern in self._pii_patterns.items():
            if pattern.search(sanitized):
                matches.append(pii_type)
                if redact:
                    sanitized = pattern.sub(f"[redacted_{pii_type}]", sanitized)
        return {
            "matched": bool(matches),
            "detail": ", ".join(matches),
            "sanitized": sanitized,
        }

    def _run_toxicity_validator(self, text: str, validator: dict[str, Any]) -> dict[str, Any]:
        lower = text.lower()
        matches = [term for term in self._toxic_terms if term in lower]
        sanitized = text
        for term in matches:
            sanitized = re.sub(re.escape(term), "[filtered_toxicity]", sanitized, flags=re.IGNORECASE)
        return {
            "matched": bool(matches),
            "detail": ", ".join(matches),
            "sanitized": sanitized,
        }
