from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


def _manifest() -> dict[str, object]:
    return {
        "employee_id": "avery",
        "org_id": "org-1",
        "employee_name": "Avery",
        "role_title": "Executive Assistant",
        "employee_type": "executive_assistant",
        "workflow": "executive_assistant",
        "tool_permissions": ["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
        "identity_layers": {
            "layer_1_core_identity": "You are a Forge AI Employee.",
            "layer_2_role_definition": "You are Avery, Executive Assistant.",
            "layer_3_organizational_map": "Support the CEO and partner closely with Sarah in operations.",
            "layer_4_behavioral_rules": "Direct commands override portal rules, which override adaptive learning.",
            "layer_5_retrieved_context": "",
            "layer_6_self_awareness": "You can coordinate scheduling, draft responses, and maintain CRM context.",
        },
        "components": [
            {"id": "workflow_executor", "category": "work", "config": {}},
            {"id": "communication_manager", "category": "work", "config": {}},
            {"id": "scheduler_manager", "category": "work", "config": {}},
            {"id": "email_tool", "category": "tools", "config": {}},
            {"id": "calendar_tool", "category": "tools", "config": {}},
            {"id": "messaging_tool", "category": "tools", "config": {}},
            {"id": "crm_tool", "category": "tools", "config": {}},
            {"id": "operational_memory", "category": "data", "config": {}},
            {"id": "working_memory", "category": "data", "config": {}},
            {"id": "context_assembler", "category": "data", "config": {}},
            {"id": "org_context", "category": "data", "config": {}},
            {"id": "audit_system", "category": "quality", "config": {}},
            {"id": "input_protection", "category": "quality", "config": {}},
        ],
        "ui": {"app_badge": "Hosted web", "capabilities": ["coordinate scheduling", "triage inbox"]},
        "org_map": [
            {"name": "Morgan CEO", "role": "Supervisor", "relationship_type": "supervisor", "communication_channel": "email"},
        ],
    }


@pytest.mark.anyio
async def test_behavior_rule_precedence_prefers_direct_commands() -> None:
    app = create_employee_app("avery", {"manifest": _manifest(), "supervisor_email": "ceo@example.com"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        adaptive = await client.post(
            "/api/v1/behavior/adaptive-patterns",
            json={
                "description": "Observed that non-urgent email can continue after 5 PM for this supervisor.",
                "after_hour": 17,
                "suppress_non_urgent": False,
                "channels": ["email"],
                "observed_for": "ceo@example.com",
            },
        )
        assert adaptive.status_code == 200

        portal = await client.post(
            "/api/v1/behavior/portal-rules",
            json={
                "description": "No non-urgent email after 5 PM.",
                "after_hour": 17,
                "suppress_non_urgent": True,
                "channels": ["email"],
            },
        )
        assert portal.status_code == 200

        resolution = await client.get(
            "/api/v1/behavior/resolution",
            params={
                "urgency": "normal",
                "channel": "email",
                "current_time": "2026-04-11T22:00:00-04:00",
            },
        )
        assert resolution.status_code == 200
        assert resolution.json()["source"] == "portal_rule"
        assert resolution.json()["suppress_non_urgent"] is True

        direct = await client.post(
            "/api/v1/behavior/direct-commands",
            json={"command": "Resume non-urgent email follow-ups after 5 PM."},
        )
        assert direct.status_code == 200

        resolution = await client.get(
            "/api/v1/behavior/resolution",
            params={
                "urgency": "normal",
                "channel": "email",
                "current_time": "2026-04-11T22:00:00-04:00",
            },
        )
        assert resolution.status_code == 200
        assert resolution.json()["source"] == "direct_command"
        assert resolution.json()["suppress_non_urgent"] is False

        rules = await client.get("/api/v1/behavior/rules")
        assert rules.status_code == 200
        assert len(rules.json()) == 3


@pytest.mark.anyio
async def test_daily_loop_respects_quiet_hours_rules() -> None:
    app = create_employee_app(
        "avery",
        {
            "manifest": _manifest(),
            "supervisor_email": "ceo@example.com",
            "deployment_format": "web",
            "email_fixtures": [
                {
                    "id": "msg-1",
                    "from": "sarah@example.com",
                    "subject": "Q2 planning",
                    "body": "Please schedule a meeting with Sarah next week and draft a short follow-up for the client.",
                    "read": False,
                },
                {
                    "id": "msg-2",
                    "from": "client@example.com",
                    "subject": "Customer success review",
                    "body": "Can you confirm tomorrow's calendar hold and prepare the customer response?",
                    "read": False,
                },
                {
                    "id": "msg-3",
                    "from": "finance@example.com",
                    "subject": "Board memo",
                    "body": "Please approve the board memo and send to all before tomorrow.",
                    "read": False,
                },
            ],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        portal = await client.post(
            "/api/v1/behavior/portal-rules",
            json={
                "description": "No non-urgent messages after 5 PM.",
                "after_hour": 17,
                "suppress_non_urgent": True,
                "channels": ["email", "messaging"],
            },
        )
        assert portal.status_code == 200

        response = await client.post(
            "/api/v1/autonomy/daily-loop",
            json={
                "conversation_id": "default",
                "max_items": 5,
                "current_time": "2026-04-11T22:00:00-04:00",
            },
        )
        assert response.status_code == 200
        report = response.json()

        assert report["metrics"]["tasks_processed"] == 3
        assert report["metrics"]["outbound_responses"] == 0
        assert report["metrics"]["supervisor_escalations"] == 1
        assert report["metrics"]["suppressed_notifications"] == 3
        assert report["metrics"]["wind_down_reports_sent"] == 0
        assert [item["response_delivery"] for item in report["processed_items"]] == ["suppressed", "suppressed", "escalated"]

    service = app.state.runtime_service
    assert len(service.components["email_tool"]._sent_messages) == 2
    assert len(service.components["messaging_tool"]._messages) == 2
