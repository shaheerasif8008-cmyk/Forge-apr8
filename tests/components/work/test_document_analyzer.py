from __future__ import annotations

import pytest

from component_library.work.document_analyzer import DocumentAnalyzer
from component_library.work.schemas import AnalysisInput, LegalIntakeInput
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
