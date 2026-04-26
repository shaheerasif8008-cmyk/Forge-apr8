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

GUARDRAILS_AVAILABLE = False
_GUARDRAILS_IMPORT_ATTEMPTED = False
_GUARDRAILS_VALIDATORS: dict[str, type[Any]] | None = None


def _load_guardrails_validators() -> dict[str, type[Any]] | None:
    global GUARDRAILS_AVAILABLE, _GUARDRAILS_IMPORT_ATTEMPTED, _GUARDRAILS_VALIDATORS

    if _GUARDRAILS_IMPORT_ATTEMPTED:
        return _GUARDRAILS_VALIDATORS

    _GUARDRAILS_IMPORT_ATTEMPTED = True
    try:
        try:
            from guardrails.hub import DetectJailbreak, DetectPII, ToxicLanguage
        except ImportError:
            from guardrails.hub import DetectPII, DetectPromptInjection, ToxicLanguage

            DetectJailbreak = DetectPromptInjection
    except ImportError:
        GUARDRAILS_AVAILABLE = False
        _GUARDRAILS_VALIDATORS = None
        return None

    GUARDRAILS_AVAILABLE = True
    _GUARDRAILS_VALIDATORS = {
        "prompt_injection": DetectJailbreak,
        "pii": DetectPII,
        "toxicity": ToxicLanguage,
    }
    return _GUARDRAILS_VALIDATORS


@register("input_protection")
class InputProtection(QualityModule):
    config_schema = {
        "validators": {"type": "list", "required": False, "description": "Explicit validator definitions overriding defaults.", "default": []},
        "validators_path": {"type": "str", "required": False, "description": "YAML file containing validator definitions.", "default": ""},
        "prompt_injection_patterns": {"type": "list", "required": False, "description": "Regex patterns used by prompt-injection fallback detection.", "default": []},
        "toxic_terms": {"type": "list", "required": False, "description": "Terms used by fallback toxicity detection.", "default": ["idiot", "stupid", "hate you"]},
        "injection_threshold": {"type": "float", "required": False, "description": "Confidence threshold for prompt injection detection (0.0-1.0).", "default": 0.8},
        "pii_detection": {"type": "bool", "required": False, "description": "Enable PII detection via Guardrails/fallback validators.", "default": True},
        "toxicity_detection": {"type": "bool", "required": False, "description": "Enable toxicity screening.", "default": True},
    }
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
        self._guardrails_validators = _load_guardrails_validators() or {}
        self._mode = "guardrails" if self._guardrails_validators else "regex_fallback"
        if self._mode == "regex_fallback":
            logger.warning(
                "input_protection_regex_fallback",
                reason="guardrails-ai not installed",
            )

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(
            healthy=True,
            detail=f"validators={len(self._validator_specs)}; mode={self._mode}",
        )

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
            result = self._run_validator(validator_id, sanitized, validator)
            if not result["matched"]:
                continue
            risk_score += severity
            if blocking:
                blocking_hits += 1
            flags.append(validator_id)
            violations.append(
                {
                    "validator": validator_id,
                    "category": validator_id,
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

    def _run_validator(self, validator_id: str, text: str, validator: dict[str, Any]) -> dict[str, Any]:
        if self._mode == "guardrails" and validator_id in self._guardrails_validators:
            return self._run_guardrails_validator(validator_id, text, validator)

        handler = getattr(self, f"_run_{validator_id}_validator", None)
        if handler is None:
            logger.warning("input_protection_unknown_validator", validator=validator_id)
            return {"matched": False, "detail": "", "sanitized": text}
        return handler(text, validator)

    def _run_guardrails_validator(
        self,
        validator_id: str,
        text: str,
        validator: dict[str, Any],
    ) -> dict[str, Any]:
        validator_cls = self._guardrails_validators[validator_id]
        guard = validator_cls(threshold=float(validator.get("severity", 0.25)))
        outcome = guard.validate(text, {"validator": validator_id, "config": validator})
        if self._guardrails_passed(outcome):
            return {"matched": False, "detail": "", "sanitized": text}

        spans = self._normalize_spans(getattr(outcome, "error_spans", []))
        detail = ", ".join(self._span_labels(spans)) or str(getattr(outcome, "reason", validator_id))
        sanitized = text
        if bool(validator.get("redact", False)):
            sanitized = self._redact_with_spans(text, spans)
            if sanitized == text and validator_id == "pii":
                sanitized = self._run_pii_validator(text, validator)["sanitized"]
        return {"matched": True, "detail": detail, "sanitized": sanitized}

    def _run_prompt_injection_validator(self, text: str, validator: dict[str, Any]) -> dict[str, Any]:
        matches: list[str] = []
        for pattern in self._prompt_patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)
        sanitized = (
            "Potential prompt injection attempt removed. No actionable business request was provided."
            if matches
            else text
        )
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

    def _guardrails_passed(self, outcome: Any) -> bool:
        status = getattr(outcome, "outcome", outcome)
        if isinstance(status, bool):
            return status
        normalized = str(getattr(status, "value", getattr(status, "name", status))).lower()
        return normalized in {"pass", "passed", "success", "valid", "true"}

    def _normalize_spans(self, spans: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for span in spans or []:
            if isinstance(span, dict):
                normalized.append(
                    {
                        "start": int(span.get("start", 0)),
                        "end": int(span.get("end", span.get("stop", 0))),
                        "text": span.get("text", ""),
                    }
                )
                continue
            normalized.append(
                {
                    "start": int(getattr(span, "start", 0)),
                    "end": int(getattr(span, "end", getattr(span, "stop", 0))),
                    "text": getattr(span, "text", ""),
                }
            )
        return normalized

    def _span_labels(self, spans: list[dict[str, Any]]) -> list[str]:
        return [str(span.get("text") or f"{span['start']}:{span['end']}") for span in spans]

    def _redact_with_spans(self, text: str, spans: list[dict[str, Any]]) -> str:
        if not spans:
            return text
        parts: list[str] = []
        cursor = 0
        for span in sorted(spans, key=lambda item: item["start"]):
            start = max(0, span["start"])
            end = max(start, span["end"])
            parts.append(text[cursor:start])
            parts.append("[redacted]")
            cursor = end
        parts.append(text[cursor:])
        return "".join(parts)
