"""Tests for factory update-control API lifecycles."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from factory.database import get_db_session
from factory.main import app
from factory.models.deployment import Deployment


async def _fake_db():
    yield object()


@pytest.fixture(autouse=True)
def fake_update_dependencies(monkeypatch):
    app.dependency_overrides[get_db_session] = _fake_db

    async def fake_get_deployment(session, deployment_id):
        return Deployment(
            id=deployment_id,
            build_id=uuid4(),
            org_id="00000000-0000-0000-0000-000000000001",
        )

    monkeypatch.setattr("factory.api.updates.get_deployment", fake_get_deployment)
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_update_controls_require_existing_deployment(client, monkeypatch) -> None:
    async def missing_deployment(session, deployment_id):
        return None

    monkeypatch.setattr("factory.api.updates.get_deployment", missing_deployment)

    response = await client.get(f"/api/v1/updates/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "deployment_not_found"


@pytest.mark.anyio
async def test_security_update_apply_delay_and_rollback_lifecycle(client) -> None:
    deployment_id = uuid4()

    response = await client.post(f"/api/v1/updates/{deployment_id}/security/sec-001/apply")

    assert response.status_code == 200
    applied = response.json()
    assert applied["update_id"] == "sec-001"
    assert applied["status"] == "applied"
    assert applied["applied_at"] is not None

    delayed_until = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    response = await client.post(
        f"/api/v1/updates/{deployment_id}/security/sec-001/delay",
        json={"delayed_until": delayed_until, "reason": "maintenance window"},
    )

    assert response.status_code == 200
    delayed = response.json()
    assert delayed["status"] == "delayed"
    assert delayed["delayed_until"] is not None
    assert delayed["delay_reason"] == "maintenance window"

    response = await client.post(
        f"/api/v1/updates/{deployment_id}/security/sec-001/delay",
        json={"delayed_until": (datetime.now(UTC) + timedelta(days=31)).isoformat()},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "security_delay_exceeds_30_days"

    response = await client.post(f"/api/v1/updates/{deployment_id}/security/sec-001/rollback")

    assert response.status_code == 200
    rolled_back = response.json()
    assert rolled_back["status"] == "rolled_back"
    assert rolled_back["rolled_back_at"] is not None


@pytest.mark.anyio
async def test_learning_updates_can_be_disabled_paused_and_resumed(client) -> None:
    deployment_id = uuid4()

    response = await client.put(f"/api/v1/updates/{deployment_id}/learning", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["paused"] is False

    response = await client.post(
        f"/api/v1/updates/{deployment_id}/learning/pause",
        json={"paused_until": (datetime.now(UTC) + timedelta(days=3)).isoformat(), "reason": "audit"},
    )

    assert response.status_code == 200
    paused = response.json()
    assert paused["enabled"] is False
    assert paused["paused"] is True
    assert paused["pause_reason"] == "audit"

    response = await client.post(f"/api/v1/updates/{deployment_id}/learning/resume")

    assert response.status_code == 200
    resumed = response.json()
    assert resumed["enabled"] is True
    assert resumed["paused"] is False
    assert resumed["paused_until"] is None


@pytest.mark.anyio
async def test_module_upgrade_preview_install_and_decline_status(client) -> None:
    deployment_id = uuid4()
    schedule_payload = {
        "component_id": "research_engine",
        "target_version": "2.0",
        "summary": "Adds citation-grounded multi-source synthesis.",
    }

    response = await client.post(f"/api/v1/updates/{deployment_id}/modules", json=schedule_payload)

    assert response.status_code == 200
    upgrade = response.json()
    assert upgrade["status"] == "scheduled"
    upgrade_id = upgrade["upgrade_id"]

    response = await client.post(f"/api/v1/updates/{deployment_id}/modules/{upgrade_id}/preview")

    assert response.status_code == 200
    assert response.json()["status"] == "previewed"
    assert response.json()["previewed_at"] is not None

    response = await client.post(f"/api/v1/updates/{deployment_id}/modules/{upgrade_id}/install")

    assert response.status_code == 200
    assert response.json()["status"] == "installed"
    assert response.json()["installed_at"] is not None

    response = await client.post(f"/api/v1/updates/{deployment_id}/modules", json=schedule_payload)
    decline_id = response.json()["upgrade_id"]

    response = await client.post(
        f"/api/v1/updates/{deployment_id}/modules/{decline_id}/decline",
        json={"reason": "not needed this quarter"},
    )

    assert response.status_code == 200
    declined = response.json()
    assert declined["status"] == "declined"
    assert declined["decline_reason"] == "not needed this quarter"


@pytest.mark.anyio
async def test_marketplace_modules_can_be_listed_and_purchased(client) -> None:
    deployment_id = uuid4()

    response = await client.get(f"/api/v1/updates/{deployment_id}/marketplace")

    assert response.status_code == 200
    modules = response.json()
    assert any(module["component_id"] == "research_engine" for module in modules)

    response = await client.post(
        f"/api/v1/updates/{deployment_id}/marketplace/research_engine/purchase",
        json={"license_type": "monthly"},
    )

    assert response.status_code == 200
    purchase = response.json()
    assert purchase["component_id"] == "research_engine"
    assert purchase["status"] == "purchased"
    assert purchase["license_type"] == "monthly"

    response = await client.get(f"/api/v1/updates/{deployment_id}")

    assert response.status_code == 200
    assert response.json()["marketplace_purchases"][0]["component_id"] == "research_engine"


@pytest.mark.anyio
async def test_policy_rules_can_be_added_listed_and_deactivated(client) -> None:
    deployment_id = uuid4()
    rule_payload = {
        "rule_id": "quiet-hours",
        "description": "Suppress non-urgent outreach after 5 PM.",
        "condition": "time_of_day > 17:00",
        "action": "suppress_non_urgent_messages",
        "priority": 2,
    }

    response = await client.post(f"/api/v1/updates/{deployment_id}/policies", json=rule_payload)

    assert response.status_code == 200
    assert response.json()["active"] is True

    response = await client.get(f"/api/v1/updates/{deployment_id}/policies")

    assert response.status_code == 200
    assert response.json()[0]["rule_id"] == "quiet-hours"
    assert response.json()[0]["active"] is True

    response = await client.post(f"/api/v1/updates/{deployment_id}/policies/quiet-hours/deactivate")

    assert response.status_code == 200
    assert response.json()["active"] is False

    response = await client.get(f"/api/v1/updates/{deployment_id}/policies")

    assert response.status_code == 200
    assert response.json()[0]["active"] is False
