from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


@pytest.mark.anyio
async def test_accountant_employee_executes_ap_aging_workflow() -> None:
    app = create_employee_app(
        "finley",
        {
            "manifest": {
                "employee_id": "finley",
                "org_id": "org-1",
                "employee_name": "Finley",
                "role_title": "AI Accountant",
                "employee_type": "executive_assistant",
                "workflow": "executive_assistant",
                "tool_permissions": ["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
                "identity_layers": {
                    "layer_1_core_identity": "You are a Forge AI Employee.",
                    "layer_2_role_definition": "You are Finley, AI Accountant.",
                    "layer_3_organizational_map": "Report to Controller.",
                    "layer_4_behavioral_rules": "Escalate high-risk cash collections.",
                    "layer_5_retrieved_context": "",
                    "layer_6_self_awareness": "You can execute AP/AR follow-ups and drafts.",
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
                    "capabilities": ["run AP/AR follow-ups", "prepare close updates"],
                },
                "org_map": [],
            }
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": (
                    "Review AP aging list and draft follow-up actions: "
                    "INV-102 is 45 days overdue for $12,400, INV-104 is 12 days overdue for $1,980."
                ),
                "context": {},
                "conversation_id": "default",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"]["title"] == "Accounting Operations Update"
    assert payload["brief"]["finance_actions"]
    assert payload["brief"]["finance_metrics"]["total_overdue_amount"] == 14380.0
    assert "INV-102" in payload["brief"]["drafted_response"]
