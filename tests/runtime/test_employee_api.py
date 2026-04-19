from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
from tests.fixtures.sample_emails import CLEAR_QUALIFIED


@pytest.mark.anyio
async def test_employee_api_task_flow() -> None:
    app = create_employee_app("arthur", {"org_id": "org-1"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200

        response = await client.post("/api/v1/tasks", json={"input": CLEAR_QUALIFIED, "context": {}, "conversation_id": "default"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"

        approvals = await client.get("/api/v1/approvals")
        assert approvals.status_code == 200


@pytest.mark.anyio
async def test_employee_api_memory_ops_and_metrics_dashboard() -> None:
    app = create_employee_app("arthur", {"org_id": "org-1"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        update = await client.patch(
            "/api/v1/memory/ops/pref:test",
            json={"value": {"channel": "email", "cadence": "daily"}, "category": "preference"},
        )
        assert update.status_code == 200
        assert update.json()["category"] == "preference"

        listing = await client.get("/api/v1/memory/ops?query=email")
        assert listing.status_code == 200
        assert any(entry["key"] == "pref:test" for entry in listing.json())

        dashboard = await client.get("/api/v1/metrics/dashboard")
        assert dashboard.status_code == 200
        assert {"kpis", "tasks_by_day", "approval_mix", "activity_mix"} <= dashboard.json().keys()

        deleted = await client.delete("/api/v1/memory/ops/pref:test")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


@pytest.mark.anyio
async def test_employee_api_knowledge_document_upload() -> None:
    app = create_employee_app(
        "kb-worker",
        {
            "manifest": {
                "employee_id": "kb-worker",
                "org_id": "org-1",
                "employee_name": "KB Worker",
                "role_title": "Knowledge Worker",
                "workflow": "executive_assistant",
                "components": [
                    {"id": "workflow_executor", "category": "work", "config": {}},
                    {"id": "communication_manager", "category": "work", "config": {}},
                    {"id": "operational_memory", "category": "data", "config": {}},
                    {"id": "working_memory", "category": "data", "config": {}},
                    {"id": "context_assembler", "category": "data", "config": {}},
                    {"id": "org_context", "category": "data", "config": {}},
                    {
                        "id": "knowledge_base",
                        "category": "data",
                        "config": {"embedder": lambda text: [0.1] * 1536},
                    },
                    {"id": "file_storage_tool", "category": "tools", "config": {"provider": "memory"}},
                    {"id": "audit_system", "category": "quality", "config": {}},
                    {"id": "input_protection", "category": "quality", "config": {}},
                ],
                "ui": {"app_badge": "Hosted web", "capabilities": ["capture documents"]},
                "org_map": [],
            }
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("playbook.txt", b"Paragraph one.\n\nParagraph two.\n\nParagraph three.", "text/plain")},
            data={"metadata": "{\"title\":\"Playbook\"}"},
        )
        assert upload.status_code == 200
        assert upload.json()["chunk_count"] == 3

        documents = await client.get("/api/v1/memory/kb/documents")
        assert documents.status_code == 200
        assert len(documents.json()) == 1
        assert documents.json()[0]["title"] == "Playbook"
