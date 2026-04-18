from __future__ import annotations

from component_library.work.schemas import (
    ConfidenceReport,
    DataAnalysisRequest,
    LegalIntakeExtraction,
    ResearchRequest,
    ScanRequest,
)


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


def test_research_request_defaults() -> None:
    request = ResearchRequest(question="What changed?")
    assert request.sources == ["web"]
    assert request.max_results == 5


def test_data_and_scan_request_defaults() -> None:
    analysis = DataAnalysisRequest(rows=[{"value": 1}])
    scan = ScanRequest(source="email")
    assert analysis.max_anomalies == 3
    assert scan.limit == 10
