from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


def _executive_assistant_manifest() -> dict[str, object]:
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
        "ui": {
            "app_badge": "Hosted web",
            "capabilities": ["coordinate scheduling", "triage inbox", "draft responses", "maintain CRM"],
        },
        "org_map": [
            {"name": "Morgan CEO", "role": "Supervisor", "relationship_type": "supervisor", "communication_channel": "email"},
            {"name": "Sarah Ops", "role": "Operations", "relationship_type": "peer", "communication_channel": "slack"},
        ],
    }


@pytest.mark.anyio
async def test_hosted_employee_daily_loop_executes_real_workflow() -> None:
    app = create_employee_app(
        "avery",
        {
            "manifest": _executive_assistant_manifest(),
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
        response = await client.post(
            "/api/v1/autonomy/daily-loop",
            json={"conversation_id": "default", "max_items": 5},
        )
        assert response.status_code == 200
        report = response.json()

        assert report["workflow"] == "executive_assistant"
        assert report["metrics"]["inbox_total"] == 3
        assert report["metrics"]["inbox_unread"] == 3
        assert report["metrics"]["tasks_processed"] == 3
        assert report["metrics"]["calendar_events_created"] >= 4
        assert report["metrics"]["crm_updates"] == 3
        assert report["metrics"]["briefings_sent"] == 1
        assert report["metrics"]["wind_down_reports_sent"] == 1
        assert report["metrics"]["outbound_responses"] == 2
        assert report["metrics"]["supervisor_escalations"] == 1
        assert len(report["processed_items"]) == 3

        latest = await client.get("/api/v1/autonomy/daily-loop/latest")
        assert latest.status_code == 200
        assert latest.json()["run_id"] == report["run_id"]

        metrics = await client.get("/api/v1/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["tasks_total"] == 3

        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200
        contents = [message["content"] for message in history.json()["messages"]]
        assert any("Morning briefing from Avery" in content for content in contents)
        assert any("Wind-down summary" in content for content in contents)

    service = app.state.runtime_service
    email_tool = service.components["email_tool"]
    calendar_tool = service.components["calendar_tool"]
    messaging_tool = service.components["messaging_tool"]
    crm_tool = service.components["crm_tool"]
    operational_memory = service.components["operational_memory"]

    assert len(email_tool._sent_messages) == 5
    assert len(calendar_tool._events) >= 4
    assert len(messaging_tool._messages) == 3
    assert sorted(crm_tool._records) == ["client@example.com", "finance@example.com", "sarah@example.com"]
    latest_report = await operational_memory.retrieve("daily_loop:latest")
    assert latest_report is not None
    assert latest_report["value"]["metrics"]["tasks_processed"] == 3
