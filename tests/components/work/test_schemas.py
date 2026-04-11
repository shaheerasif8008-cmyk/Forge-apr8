from __future__ import annotations

from component_library.work.schemas import ConfidenceReport, LegalIntakeExtraction


def test_legal_intake_extraction_defaults() -> None:
    extraction = LegalIntakeExtraction()
    assert extraction.urgency == "normal"
    assert extraction.key_facts == []


def test_confidence_report_shape() -> None:
    report = ConfidenceReport(
        overall_score=0.8,
        llm_self_assessment=0.75,
        structural_score=0.85,
        recommendation="proceed",
    )
    assert report.recommendation == "proceed"
