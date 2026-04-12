from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


@pytest.mark.anyio
async def test_executive_assistant_runtime_flow() -> None:
    app = create_employee_app(
        "avery",
        {
            "manifest": {
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
                    "layer_3_organizational_map": "Support the CEO.",
                    "layer_4_behavioral_rules": "Escalate approvals.",
                    "layer_5_retrieved_context": "",
                    "layer_6_self_awareness": "You can coordinate scheduling and communications.",
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
                    "capabilities": ["coordinate scheduling", "draft responses"],
                },
                "org_map": [],
            }
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        meta = await client.get("/api/v1/meta")
        assert meta.status_code == 200
        assert meta.json()["workflow"] == "executive_assistant"

        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": "Please schedule a meeting with Sarah next week and draft a short follow-up.",
                "context": {},
                "conversation_id": "default",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["brief"]["title"] == "Executive Assistant Update"
        assert payload["brief"]["schedule_updates"]
