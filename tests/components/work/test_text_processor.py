from __future__ import annotations

import pytest

from component_library.models.litellm_router import TaskType
from component_library.work.schemas import LegalIntakeInput
from component_library.work.text_processor import TextProcessor
from tests.fixtures.sample_emails import (
    AMBIGUOUS,
    CLEAR_QUALIFIED,
    POTENTIAL_CONFLICT,
    URGENT,
)


@pytest.mark.anyio
async def test_text_processor_extracts_clear_qualified_email() -> None:
    component = TextProcessor()
    await component.initialize({})
    result = await component.execute(LegalIntakeInput(email_text=CLEAR_QUALIFIED))
    assert result.client_name == "Sarah Johnson"
    assert "personal injury" in result.matter_type or "car accident" in result.raw_summary.lower()
    assert result.extraction_confidence >= 0.8


@pytest.mark.anyio
async def test_text_processor_handles_ambiguous_email() -> None:
    component = TextProcessor()
    await component.initialize({})
    result = await component.execute(LegalIntakeInput(email_text=AMBIGUOUS))
    assert result.client_name in {"", "Mike"}
    assert result.extraction_confidence < 0.7


@pytest.mark.anyio
async def test_text_processor_extracts_conflict_and_urgency() -> None:
    component = TextProcessor()
    await component.initialize({})
    conflict_result = await component.execute(LegalIntakeInput(email_text=POTENTIAL_CONFLICT))
    urgent_result = await component.execute(LegalIntakeInput(email_text=URGENT))
    assert any("Anderson" in item for item in conflict_result.potential_conflicts)
    assert urgent_result.urgency == "urgent"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("email_text", "matter_type"),
    [
        (
            "This is Elena Torres. I think my employer discriminated against me after I reported harassment at work.",
            "employment",
        ),
        (
            "My name is Dana Lee. I slipped at a grocery store and broke my wrist. The store manager was John Evans.",
            "personal injury",
        ),
        (
            "My name is Priya Shah. Our company has a breach of contract dispute with North Coast Manufacturing over a supply agreement.",
            "commercial dispute",
        ),
    ],
)
async def test_text_processor_extracts_evaluator_qualified_matters(email_text: str, matter_type: str) -> None:
    component = TextProcessor()
    await component.initialize({})
    result = await component.execute(LegalIntakeInput(email_text=email_text))

    assert result.matter_type == matter_type
    assert result.client_name
    assert result.key_facts


class _FakeRouter:
    component_id = "litellm_router"

    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def complete_structured(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


@pytest.mark.anyio
async def test_text_processor_prefers_llm_when_router_is_available() -> None:
    component = TextProcessor()
    await component.initialize({"force_llm": True})
    router = _FakeRouter(
        component._extract_deterministic(CLEAR_QUALIFIED).model_copy(update={"raw_summary": "LLM extraction summary."})
    )
    component.set_model_client(router)
    result = await component.execute(LegalIntakeInput(email_text=CLEAR_QUALIFIED))

    assert result.raw_summary == "LLM extraction summary."
    assert len(router.calls) == 1
    assert router.calls[0][0][0] == TaskType.STRUCTURED
