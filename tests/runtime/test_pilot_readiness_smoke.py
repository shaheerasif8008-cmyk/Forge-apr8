from __future__ import annotations

import pytest

from scripts.pilot_readiness_smoke import run_pilot_smoke


@pytest.mark.anyio
async def test_pilot_readiness_smoke_exercises_launch_runtime_surfaces() -> None:
    report = await run_pilot_smoke()

    assert report["overall"] == "passed"
    assert report["production_guards"]["auth_required"] is True
    assert report["production_guards"]["unauthorized_status"] == 401

    check_names = {check["name"] for check in report["checks"]}
    assert {
        "health_public",
        "auth_unauthorized",
        "auth_authorized_history",
        "meta",
        "task_submit",
        "task_brief",
        "correction",
        "memory_update",
        "settings_patch",
        "behavior_direct_command",
        "document_upload",
        "daily_loop",
        "metrics_dashboard",
        "updates",
        "integration_degraded_inventory",
    } <= check_names

    assert all(check["status"] == "passed" for check in report["checks"])
    assert any(item["component_id"] == "email_tool" for item in report["degraded_integrations"])
    assert report["degraded_integrations_policy"] == "allowed_for_pilot_with_disclosure"
