from __future__ import annotations

import pytest

from component_library.models.litellm_router import TaskType
from component_library.work.document_analyzer import DocumentAnalyzer
from component_library.work.schemas import AnalysisInput, DocumentAnalyzerOutput, LegalIntakeInput
from component_library.work.text_processor import TextProcessor
from tests.fixtures.sample_emails import AMBIGUOUS, CLEAR_QUALIFIED, CLEAR_UNQUALIFIED


async def _extract(email_text: str):
    processor = TextProcessor()
    await processor.initialize({})
    return await processor.execute(LegalIntakeInput(email_text=email_text))


@pytest.mark.anyio
async def test_document_analyzer_qualified_case() -> None:
    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["personal injury"]})
    extraction = await _extract(CLEAR_QUALIFIED)
    result = await analyzer.execute(AnalysisInput(extraction=extraction))
    assert result.qualification_decision == "qualified"


@pytest.mark.anyio
async def test_document_analyzer_unqualified_case() -> None:
    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["personal injury"]})
    extraction = await _extract(CLEAR_UNQUALIFIED)
    result = await analyzer.execute(AnalysisInput(extraction=extraction))
    assert result.qualification_decision == "not_qualified"


@pytest.mark.anyio
async def test_document_analyzer_needs_review_case() -> None:
    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["employment"]})
    extraction = await _extract(AMBIGUOUS)
    result = await analyzer.execute(AnalysisInput(extraction=extraction))
    assert result.qualification_decision == "needs_review"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "email_text",
    [
        "My name is Sarah Johnson. I was injured in a car accident on February 15, 2026 and need help pursuing a personal injury claim. You can reach me at sarah.johnson@email.com.",
        "My name is Priya Shah. Our company has a breach of contract dispute with North Coast Manufacturing over a supply agreement.",
        "This is Elena Torres. I think my employer discriminated against me after I reported harassment at work.",
        "My name is Dana Lee. I slipped at a grocery store and broke my wrist. The store manager was John Evans.",
    ],
)
async def test_document_analyzer_qualifies_clear_evaluator_matters(email_text: str) -> None:
    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["personal injury", "employment", "commercial dispute"]})
    extraction = await _extract(email_text)
    result = await analyzer.execute(AnalysisInput(extraction=extraction))

    assert result.qualification_decision == "qualified"


@pytest.mark.anyio
async def test_document_analyzer_corrects_conservative_model_decision() -> None:
    extraction = await _extract(
        "My name is Dana Lee. I slipped at a grocery store and broke my wrist. The store manager was John Evans."
    )
    analyzer = DocumentAnalyzer()
    await analyzer.initialize(
        {
            "practice_areas": ["personal injury", "employment", "commercial dispute"],
            "force_llm": True,
        }
    )
    analyzer.set_model_client(
        _FakeRouter(
            DocumentAnalyzerOutput(
                summary="Conservative model summary.",
                key_findings=["The prospect describes an injury at a grocery store."],
                risk_flags=["Missing direct contact information for immediate follow-up."],
                recommended_actions=["Request more information."],
                qualification_decision="not_qualified",
                qualification_reasoning="The model was too conservative.",
                confidence=0.72,
            )
        )
    )

    result = await analyzer.execute(AnalysisInput(extraction=extraction))

    assert result.qualification_decision == "qualified"
    assert "Missing direct contact information" in result.risk_flags


class _FakeRouter:
    component_id = "litellm_router"

    def __init__(self, response: DocumentAnalyzerOutput) -> None:
        self.response = response
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def complete_structured(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


@pytest.mark.anyio
async def test_document_analyzer_prefers_llm_when_router_is_available() -> None:
    analyzer = DocumentAnalyzer()
    await analyzer.initialize({"practice_areas": ["personal injury"], "force_llm": True})
    analyzer.set_model_client(
        _FakeRouter(
            DocumentAnalyzerOutput(
                summary="LLM analysis summary.",
                key_findings=["Matter fits the firm's intake profile."],
                risk_flags=[],
                recommended_actions=["Schedule consultation."],
                qualification_decision="qualified",
                qualification_reasoning="The extracted facts match the firm's stated practice area.",
                confidence=0.91,
            )
        )
    )
    extraction = await _extract(CLEAR_QUALIFIED)
    result = await analyzer.execute(AnalysisInput(extraction=extraction))

    assert result.summary == "LLM analysis summary."
    assert result.qualification_decision == "qualified"
    assert analyzer._model_client.calls[0][0][0] == TaskType.STRUCTURED
