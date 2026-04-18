from __future__ import annotations

import pytest

from component_library.quality.autonomy_manager import AutonomyManager


@pytest.mark.anyio
async def test_reversible_low_risk_high_confidence_is_autonomous() -> None:
    events: list[dict[str, object]] = []

    async def audit_logger(**kwargs):
        events.append(kwargs)

    manager = AutonomyManager()
    await manager.initialize({"audit_logger": audit_logger})
    decision = await manager.evaluate(
        {
            "action": {
                "type": "reversible",
                "description": "check inbox",
                "confidence": 0.95,
                "estimated_impact": {"recipients": 0},
            },
            "context": {"risk_tier": "LOW", "tenant_policy": {"org_id": "org-1"}},
        }
    )
    assert decision.mode == "autonomous"
    assert decision.matched_rule == "default_autonomous"
    assert events[-1]["event_type"] == "autonomy_decision"


@pytest.mark.anyio
async def test_irreversible_high_risk_requires_approval() -> None:
    manager = AutonomyManager()
    await manager.initialize({})
    decision = await manager.evaluate(
        {
            "action": {
                "type": "irreversible",
                "description": "send outbound email",
                "confidence": 0.99,
                "estimated_impact": {"recipients": 1},
            },
            "context": {"risk_tier": "HIGH", "tenant_policy": {}},
        }
    )
    assert decision.mode == "approval_required"
    assert decision.required_approver == "supervisor"


@pytest.mark.anyio
async def test_critical_risk_always_escalates() -> None:
    manager = AutonomyManager()
    await manager.initialize({})
    decision = await manager.evaluate(
        {
            "action": {
                "type": "reversible",
                "description": "mark read",
                "confidence": 0.2,
                "estimated_impact": {},
            },
            "context": {"risk_tier": "CRITICAL", "tenant_policy": {}},
        }
    )
    assert decision.mode == "escalate"
    assert decision.required_approver == "supervisor"


@pytest.mark.anyio
async def test_reversible_medium_risk_low_confidence_requires_approval() -> None:
    manager = AutonomyManager()
    await manager.initialize({})
    decision = await manager.evaluate(
        {
            "action": {
                "type": "reversible",
                "description": "check inbox",
                "confidence": 0.45,
                "estimated_impact": {},
            },
            "context": {"risk_tier": "MEDIUM", "tenant_policy": {}},
        }
    )
    assert decision.mode == "approval_required"
    assert decision.matched_rule == "reversible_medium_low_conf"


@pytest.mark.anyio
async def test_tenant_policy_override_forces_approval() -> None:
    manager = AutonomyManager()
    await manager.initialize({})
    decision = await manager.evaluate(
        {
            "action": {
                "type": "reversible",
                "description": "check inbox",
                "confidence": 1.0,
                "estimated_impact": {},
            },
            "context": {
                "risk_tier": "LOW",
                "tenant_policy": {"force_approval_all": True, "required_approver": "general_counsel"},
            },
        }
    )
    assert decision.mode == "approval_required"
    assert decision.required_approver == "general_counsel"
    assert decision.matched_rule == "tenant_override.force_approval_all"
