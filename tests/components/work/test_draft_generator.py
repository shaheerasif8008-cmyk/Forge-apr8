from __future__ import annotations

import pytest

from component_library.models.litellm_router import TaskType
from component_library.work.document_analyzer import DocumentAnalyzer
from component_library.work.draft_generator import DraftGenerator
from component_library.work.schemas import (
    AnalysisInput,
    ConfidenceReport,
    DraftInput,
    IntakeBrief,
    LegalIntakeInput,
)
from component_library.work.text_processor import TextProcessor
from tests.fixtures.sample_emails import CLEAR_QUALIFIED


async def _draft_input() -> DraftInput:
    processor = TextProcessor()
    await processor.initialize({})
    extraction = await processor.execute(LegalIntakeInput(email_text=CLEAR_QUALIFIED))

    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["personal injury"]})
    analysis = await analyzer.execute(AnalysisInput(extraction=extraction))
    return DraftInput(
        extraction=extraction,
        analysis=analysis,
        confidence_report=ConfidenceReport(
            overall_score=0.89,
            llm_self_assessment=0.9,
            structural_score=0.88,
            dimension_scores={"completeness": 0.9},
            flags=[],
            recommendation="proceed",
        ),
    )


class _FakeRouter:
    component_id = "litellm_router"

    def __init__(self, response: IntakeBrief) -> None:
        self.response = response
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def complete_structured(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


@pytest.mark.anyio
async def test_draft_generator_deterministic_output() -> None:
    generator = DraftGenerator()
    await generator.initialize({"default_attorney": "Arthur Review"})
    result = await generator.execute(await _draft_input())

    assert result.recommended_attorney == "Arthur Review"
    assert result.executive_summary
    assert result.next_steps


@pytest.mark.anyio
async def test_draft_generator_prefers_llm_when_router_is_available() -> None:
    generator = DraftGenerator()
    await generator.initialize({"default_attorney": "Arthur Review", "force_llm": True})
    draft_input = await _draft_input()
    generator.set_model_client(
        _FakeRouter(
            IntakeBrief(
                client_info=draft_input.extraction,
                analysis=draft_input.analysis,
                confidence_score=draft_input.confidence_report.overall_score,
                executive_summary="LLM-generated executive summary.",
                recommended_attorney="Arthur Review",
                recommended_practice_area=draft_input.extraction.matter_type,
                next_steps=["Schedule consultation.", "Collect accident records."],
                flags=["urgent follow-up"],
            )
        )
    )

    result = await generator.execute(draft_input)

    assert result.executive_summary == "LLM-generated executive summary."
    assert result.flags == ["urgent follow-up"]
    assert generator._model_client.calls[0][0][0] == TaskType.STRUCTURED
