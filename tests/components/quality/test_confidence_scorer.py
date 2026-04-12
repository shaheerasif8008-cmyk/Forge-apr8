from __future__ import annotations

import pytest

from component_library.quality.confidence_scorer import ConfidenceScorer
from component_library.work.schemas import (
    ConfidenceInput,
    DocumentAnalyzerOutput,
    LegalIntakeExtraction,
)


@pytest.mark.anyio
async def test_confidence_scorer_returns_report() -> None:
    scorer = ConfidenceScorer()
    await scorer.initialize({})
    report = scorer.score(
        ConfidenceInput(
            extraction=LegalIntakeExtraction(client_name="Sarah", matter_type="personal injury", client_email="sarah@example.com", extraction_confidence=0.8),
            analysis=DocumentAnalyzerOutput(
                summary="Qualified",
                key_findings=["Strong damages"],
                risk_flags=[],
                recommended_actions=["Schedule consultation"],
                qualification_decision="qualified",
                qualification_reasoning="Looks like a fit.",
                confidence=0.82,
            ),
        )
    )
    assert report.overall_score > 0.6
