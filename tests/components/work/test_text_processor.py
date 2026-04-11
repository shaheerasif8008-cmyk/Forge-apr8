from __future__ import annotations

import pytest

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
