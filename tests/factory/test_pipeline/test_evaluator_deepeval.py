from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import pytest

import factory.pipeline.evaluator.deepeval_adapter as deepeval_adapter
from factory.pipeline.evaluator.behavioral_tests import run_behavioral_tests
from factory.pipeline.evaluator.functional_tests import run_functional_tests
from factory.pipeline.evaluator.hallucination_tests import run_hallucination_tests


class _Response:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, path: str, json: dict[str, Any]) -> _Response:
        if path == "/api/v1/tasks":
            text = json["input"]
            lower = text.lower()
            if "parking ticket" in lower or "custody" in lower or "real estate" in lower:
                decision = "not_qualified"
                matter = "parking ticket" if "parking ticket" in lower else "family law" if "custody" in lower else "real estate"
            elif "not sure" in lower or "do not want to get into details" in lower:
                decision = "needs_review"
                matter = ""
            elif "employer" in lower or "terminated" in lower or "harassment" in lower:
                decision = "qualified"
                matter = "employment"
            elif "contract" in lower or "supply agreement" in lower:
                decision = "qualified"
                matter = "commercial dispute"
            else:
                decision = "qualified"
                matter = "personal injury"
            name = _extract_name(text)
            email = _extract_email(text)
            phone = _extract_phone(text)
            payload = {
                "brief": {
                    "client_info": {
                        "client_name": name.strip(),
                        "client_email": email,
                        "client_phone": phone,
                        "matter_type": matter,
                        "opposing_party": "",
                    },
                    "analysis": {"qualification_decision": decision},
                    "confidence_score": 0.8,
                    "executive_summary": "Neutral summary.",
                }
            }
            return _Response(200, payload)
        raise AssertionError(f"Unexpected POST path: {path}")

    async def put(self, path: str, json: dict[str, Any]) -> _Response:
        if path == "/api/v1/settings":
            return _Response(200, {"quiet_hours": json["values"]["quiet_hours"]})
        raise AssertionError(f"Unexpected PUT path: {path}")

    async def get(self, path: str) -> _Response:
        if path == "/api/v1/approvals":
            return _Response(200, [])
        if path == "/api/v1/metrics":
            return _Response(200, {"tasks_total": 3})
        raise AssertionError(f"Unexpected GET path: {path}")


def _extract_name(text: str) -> str:
    patterns = [
        r"My name is ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"Hello, this is ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"This is ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"Hi, I'm ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"I'm ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    tail_match = re.search(r"\n([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*$", text)
    return tail_match.group(1) if tail_match else "Unknown"


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    return match.group(0) if match else ""


def test_metrics_use_deepeval_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeLLMTestCase:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class _FakeAnswerMetric:
        def __init__(self, *, model: str) -> None:
            captured["model"] = model

        def measure(self, test_case: _FakeLLMTestCase) -> None:
            captured["test_case"] = test_case
            self.score = 0.84
            self.success = True
            self.reason = "relevant"

    monkeypatch.setattr(deepeval_adapter, "DEEPEVAL_AVAILABLE", True)
    monkeypatch.setattr(deepeval_adapter, "AnswerRelevancyMetric", _FakeAnswerMetric)
    monkeypatch.setattr(deepeval_adapter, "LLMTestCase", _FakeLLMTestCase)
    monkeypatch.setattr(
        deepeval_adapter,
        "get_settings",
        lambda: SimpleNamespace(llm_safety_model="judge-model", generator_model="generator-model"),
    )

    result = deepeval_adapter.answer_relevancy_metric(
        {"brief": {"analysis": {"qualification_decision": "qualified"}}},
        "qualified",
    )

    assert result.passed is True
    assert 0.0 <= result.score <= 1.0
    assert captured["model"] == "judge-model"
    assert isinstance(captured["test_case"], _FakeLLMTestCase)


def test_metrics_fall_back_when_deepeval_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deepeval_adapter, "DEEPEVAL_AVAILABLE", False)
    monkeypatch.setattr(deepeval_adapter, "AnswerRelevancyMetric", None)
    monkeypatch.setattr(deepeval_adapter, "LLMTestCase", None)

    result = deepeval_adapter.answer_relevancy_metric(
        {"brief": {"analysis": {"qualification_decision": "qualified"}}},
        "qualified",
    )

    assert result.as_dict().keys() == {"name", "score", "passed", "detail"}
    assert 0.0 <= result.score <= 1.0
    assert result.passed is True


@pytest.mark.anyio
async def test_functional_deepeval_suite(monkeypatch) -> None:
    monkeypatch.setattr("factory.pipeline.evaluator.functional_tests.httpx.AsyncClient", _FakeAsyncClient)
    result = await run_functional_tests("http://test")
    assert result["tests"] > 10
    assert result["passed"] is True
    assert result["cases"]


@pytest.mark.anyio
async def test_behavioral_and_hallucination_suites(monkeypatch) -> None:
    monkeypatch.setattr("factory.pipeline.evaluator.behavioral_tests.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("factory.pipeline.evaluator.hallucination_tests.httpx.AsyncClient", _FakeAsyncClient)
    behavioral = await run_behavioral_tests("http://test")
    hallucination = await run_hallucination_tests("http://test")
    assert behavioral["passed"] is True
    assert hallucination["passed"] is True
    assert hallucination["cases"]
