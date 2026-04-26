"""DeepEval metric adapters with deterministic fallbacks when the package is absent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from factory.config import get_settings

logger = structlog.get_logger(__name__)

DEEPEVAL_AVAILABLE = False
AnswerRelevancyMetric: type[Any] | None = None
FaithfulnessMetric: type[Any] | None = None
HallucinationMetric: type[Any] | None = None
LLMTestCase: type[Any] | None = None

try:  # pragma: no cover - depends on optional dependency
    from deepeval.metrics import AnswerRelevancyMetric as _AnswerRelevancyMetric
    from deepeval.metrics import FaithfulnessMetric as _FaithfulnessMetric
    from deepeval.metrics import HallucinationMetric as _HallucinationMetric
    from deepeval.test_case import LLMTestCase as _LLMTestCase

    AnswerRelevancyMetric = _AnswerRelevancyMetric
    FaithfulnessMetric = _FaithfulnessMetric
    HallucinationMetric = _HallucinationMetric
    LLMTestCase = _LLMTestCase
    DEEPEVAL_AVAILABLE = True
except ImportError:  # pragma: no cover - deterministic fallback path is tested instead
    logger.warning("deepeval_adapter_fallback", reason="deepeval not installed")


@dataclass
class MetricResult:
    name: str
    score: float
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "passed": self.passed,
            "detail": self.detail,
        }


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def json_schema_metric(payload: dict[str, Any]) -> MetricResult:
    """Validate the expected response shape; this remains intentionally hand-rolled."""
    brief = payload.get("brief", {})
    required = ["client_info", "analysis", "confidence_score"]
    missing = [field for field in required if field not in brief]
    return MetricResult(
        name="json_schema",
        score=1.0 if not missing else 0.0,
        passed=not missing,
        detail="schema ok" if not missing else f"missing fields: {', '.join(missing)}",
    )


def answer_relevancy_metric(payload: dict[str, Any], expected_decision: str) -> MetricResult:
    if not DEEPEVAL_AVAILABLE or AnswerRelevancyMetric is None or LLMTestCase is None:
        return _fallback_answer_relevancy_metric(payload, expected_decision)

    actual = payload.get("brief", {}).get("analysis", {}).get("qualification_decision", "")
    test_case = LLMTestCase(
        input="Determine the correct qualification decision for the intake.",
        actual_output=str(actual),
        expected_output=str(expected_decision),
        retrieval_context=[],
    )
    metric = AnswerRelevancyMetric(model=_judge_model())
    try:
        return _run_deepeval_metric("answer_relevancy", metric, test_case)
    except Exception as exc:  # pragma: no cover - depends on optional deepeval internals
        logger.warning("deepeval_metric_fallback", metric="answer_relevancy", reason=str(exc))
        return _fallback_answer_relevancy_metric(payload, expected_decision)


def faithfulness_metric(payload: dict[str, Any], case: dict[str, Any]) -> MetricResult:
    if not DEEPEVAL_AVAILABLE or FaithfulnessMetric is None or LLMTestCase is None:
        return _fallback_faithfulness_metric(payload, case)

    actual = json.dumps(payload.get("brief", {}).get("client_info", {}), sort_keys=True)
    expected = json.dumps(
        {
            "client_name": case.get("client_name", ""),
            "matter_type": case.get("matter_type", ""),
        },
        sort_keys=True,
    )
    test_case = LLMTestCase(
        input=str(case.get("input", "")),
        actual_output=actual,
        expected_output=expected,
        retrieval_context=[str(case.get("input", ""))],
    )
    metric = FaithfulnessMetric(model=_judge_model())
    try:
        return _run_deepeval_metric("faithfulness", metric, test_case)
    except Exception as exc:  # pragma: no cover - depends on optional deepeval internals
        logger.warning("deepeval_metric_fallback", metric="faithfulness", reason=str(exc))
        return _fallback_faithfulness_metric(payload, case)


def hallucination_metric(payload: dict[str, Any], source_text: str) -> MetricResult:
    if not DEEPEVAL_AVAILABLE or HallucinationMetric is None or LLMTestCase is None:
        return _fallback_hallucination_metric(payload, source_text)

    actual = json.dumps(payload.get("brief", {}).get("client_info", {}), sort_keys=True)
    test_case = LLMTestCase(
        input=source_text,
        actual_output=actual,
        expected_output=source_text,
        retrieval_context=[source_text],
    )
    metric = HallucinationMetric(model=_judge_model())
    try:
        return _run_deepeval_metric("hallucination", metric, test_case)
    except Exception as exc:  # pragma: no cover - depends on optional deepeval internals
        logger.warning("deepeval_metric_fallback", metric="hallucination", reason=str(exc))
        return _fallback_hallucination_metric(payload, source_text)


def toxicity_metric(text: str) -> MetricResult:
    toxic_terms = ["idiot", "stupid", "hate you", "moron"]
    lower = text.lower()
    matches = [term for term in toxic_terms if term in lower]
    score = min(1.0, len(matches) * 0.5)
    return MetricResult(
        name="toxicity",
        score=score,
        passed=not matches,
        detail="matches: " + (", ".join(matches) if matches else "none"),
    )


def bias_metric(text: str) -> MetricResult:
    bias_terms = ["those people", "your kind", "obviously women", "obviously men"]
    lower = text.lower()
    matches = [term for term in bias_terms if term in lower]
    score = min(1.0, len(matches) * 0.5)
    return MetricResult(
        name="bias",
        score=score,
        passed=not matches,
        detail="matches: " + (", ".join(matches) if matches else "none"),
    )


def _judge_model() -> str:
    settings = get_settings()
    return settings.llm_safety_model or settings.generator_model


def _run_deepeval_metric(name: str, metric: Any, test_case: Any) -> MetricResult:
    metric.measure(test_case)
    return MetricResult(
        name=name,
        score=float(getattr(metric, "score", 0.0)),
        passed=bool(getattr(metric, "success", False)),
        detail=str(getattr(metric, "reason", "")),
    )


def _fallback_answer_relevancy_metric(payload: dict[str, Any], expected_decision: str) -> MetricResult:
    actual = payload.get("brief", {}).get("analysis", {}).get("qualification_decision", "")
    passed = actual == expected_decision
    return MetricResult(
        name="answer_relevancy",
        score=1.0 if passed else 0.0,
        passed=passed,
        detail=f"expected={expected_decision} actual={actual}",
    )


def _fallback_faithfulness_metric(payload: dict[str, Any], case: dict[str, Any]) -> MetricResult:
    extraction = payload.get("brief", {}).get("client_info", {})
    supported = 0
    checks = 0
    for field in ("client_name", "matter_type"):
        expected = str(case.get(field, "")).strip()
        if not expected:
            continue
        checks += 1
        if str(extraction.get(field, "")).strip().lower() == expected.lower():
            supported += 1
    score = 1.0 if checks == 0 else supported / checks
    return MetricResult(
        name="faithfulness",
        score=score,
        passed=score >= 0.5,
        detail=f"supported={supported}/{checks}",
    )


def _fallback_hallucination_metric(payload: dict[str, Any], source_text: str) -> MetricResult:
    source_lower = source_text.lower()
    extraction = payload.get("brief", {}).get("client_info", {})
    claims = [
        str(extraction.get("client_name", "")).strip(),
        str(extraction.get("client_email", "")).strip(),
        str(extraction.get("client_phone", "")).strip(),
        str(extraction.get("opposing_party", "")).strip(),
    ]
    claims = [claim for claim in claims if claim]
    unsupported = [claim for claim in claims if claim.lower() not in source_lower]
    score = 0.0 if not claims else len(unsupported) / len(claims)
    return MetricResult(
        name="hallucination",
        score=score,
        passed=score <= 0.35,
        detail="unsupported claims: " + (", ".join(unsupported) if unsupported else "none"),
    )
