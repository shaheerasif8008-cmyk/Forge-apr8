from __future__ import annotations

import pytest

from component_library.quality.verification_layer import VerificationLayer
from component_library.work.schemas import (
    DocumentAnalyzerOutput,
    IntakeBrief,
    LegalIntakeExtraction,
    VerificationInput,
)


@pytest.mark.anyio
async def test_verification_layer_validates_brief() -> None:
    layer = VerificationLayer()
    await layer.initialize({})
    brief = IntakeBrief(
        client_info=LegalIntakeExtraction(client_name="Sarah", matter_type="personal injury", client_email="sarah@example.com"),
        analysis=DocumentAnalyzerOutput(
            summary="Qualified",
            key_findings=[],
            risk_flags=[],
            recommended_actions=[],
            qualification_decision="qualified",
            qualification_reasoning="Fit",
            confidence=0.8,
        ),
        confidence_score=0.8,
    )
    result = layer.verify(VerificationInput(brief=brief))
    assert result.is_valid is True
