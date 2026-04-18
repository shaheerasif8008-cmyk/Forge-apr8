from __future__ import annotations

import pytest

from component_library.quality.compliance_rules import ComplianceRules


@pytest.mark.anyio
async def test_legal_policy_allows_clean_email() -> None:
    rules = ComplianceRules()
    await rules.initialize({"policy_name": "legal", "conflicts": ["Acme Corp"]})
    decision = await rules.evaluate(
        {
            "action_type": "email_send",
            "content": "We received your documents and will route them for review.",
            "entities": [],
        }
    )
    assert decision.allowed is True
    assert decision.violations == []


@pytest.mark.anyio
async def test_legal_policy_rejects_direct_legal_advice() -> None:
    rules = ComplianceRules()
    await rules.initialize({"policy_name": "legal"})
    decision = await rules.evaluate(
        {
            "action_type": "email_send",
            "content": "You should sue immediately and I recommend filing this week.",
            "entities": [],
        }
    )
    assert decision.allowed is False
    assert any("legal advice" in violation.lower() for violation in decision.violations)


@pytest.mark.anyio
async def test_legal_policy_rejects_known_conflict() -> None:
    rules = ComplianceRules()
    await rules.initialize({"policy_name": "legal", "conflicts": ["Acme Corp"]})
    decision = await rules.evaluate(
        {
            "action_type": "email_send",
            "content": "Routing this matter for intake review.",
            "entities": ["Acme Corp"],
        }
    )
    assert decision.allowed is False
    assert any("conflict" in violation.lower() for violation in decision.violations)


@pytest.mark.anyio
async def test_healthcare_policy_requires_phi_scrubbing() -> None:
    rules = ComplianceRules()
    await rules.initialize({"policy_name": "healthcare"})
    decision = await rules.evaluate(
        {
            "content": "Patient Jane Doe diagnosis and DOB are attached.",
            "scrubbed": False,
        }
    )
    assert decision.allowed is False
    assert any("phi" in violation.lower() for violation in decision.violations)
