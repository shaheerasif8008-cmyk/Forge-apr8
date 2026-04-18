from __future__ import annotations

import pytest

from component_library.tools.email_tool import EmailTool
from component_library.work.monitor_scanner import MonitorScanner
from component_library.work.schemas import ScanRequest


class _MockStructuredModel:
    component_id = "custom-model"

    def __init__(self) -> None:
        self.calls = 0

    async def complete_structured(self, system_prompt: str, user_message: str, output_model):
        self.calls += 1
        return output_model(
            relevant=True,
            raw_score=0.93,
            rationale="LLM judged this urgent.",
            summary="Urgent signal",
        )


@pytest.mark.anyio
async def test_monitor_scanner_email_happy_path() -> None:
    email = EmailTool()
    await email.initialize(
        {
            "fixtures": [
                {"id": "1", "subject": "Urgent contract deadline", "read": False},
                {"id": "2", "subject": "Lunch plans", "read": False},
            ]
        }
    )
    scanner = MonitorScanner()
    await scanner.initialize({"email_tool": email})
    signals = await scanner.scan(
        ScanRequest(source="email", query="contract", criteria=["urgent"])
    )
    assert signals
    assert signals[0].source == "email"
    assert signals[0].raw_score > 0


@pytest.mark.anyio
async def test_monitor_scanner_empty_input() -> None:
    scanner = MonitorScanner()
    await scanner.initialize({})
    signals = await scanner.scan(ScanRequest(source="email"))
    assert signals == []


@pytest.mark.anyio
async def test_monitor_scanner_unsupported_source_errors() -> None:
    scanner = MonitorScanner()
    await scanner.initialize({})
    with pytest.raises(ValueError, match="Unsupported signal source"):
        await scanner.scan(ScanRequest(source="unknown"))


@pytest.mark.anyio
async def test_monitor_scanner_uses_llm_classifier_when_forced() -> None:
    model = _MockStructuredModel()
    scanner = MonitorScanner()
    await scanner.initialize({"model_client": model, "force_llm": True})
    signals = await scanner.scan(
        ScanRequest(
            source="email",
            raw_items=[{"subject": "Need approval", "timestamp": "2026-04-18T12:00:00Z"}],
        )
    )
    assert signals[0].raw_score == 0.93
    assert model.calls == 1
