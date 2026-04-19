from __future__ import annotations

import asyncio
import contextlib

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
from employee_runtime.core.conversation_repository import InMemoryConversationRepository
from employee_runtime.core.task_repository import InMemoryTaskRepository
from tests.fixtures.sample_emails import AMBIGUOUS, CLEAR_QUALIFIED


def _executive_manifest() -> dict[str, object]:
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
            "layer_3_organizational_map": "Support the CEO and coordinate with operations.",
            "layer_4_behavioral_rules": "Direct commands override portal rules, which override adaptive learning.",
            "layer_5_retrieved_context": "",
            "layer_6_self_awareness": "You can coordinate schedules, draft responses, and maintain CRM context.",
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
        "ui": {"app_badge": "Hosted web", "capabilities": ["coordinate scheduling", "draft responses"]},
        "org_map": [{"name": "Morgan CEO", "role": "Supervisor", "relationship_type": "supervisor", "communication_channel": "email"}],
    }


@pytest.mark.anyio
async def test_chat_history_survives_service_reinitialization() -> None:
    repository = InMemoryConversationRepository()
    app_one = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})

    async with AsyncClient(transport=ASGITransport(app=app_one), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={"input": CLEAR_QUALIFIED, "context": {}, "conversation_id": "default"},
        )
        assert response.status_code == 200

    app_two = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})
    async with AsyncClient(transport=ASGITransport(app=app_two), base_url="http://test") as client:
        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert any(message["role"] == "user" and CLEAR_QUALIFIED in message["content"] for message in messages)
        assert any(message["message_type"] == "status_update" for message in messages)


@pytest.mark.anyio
async def test_pending_approvals_recover_after_restart() -> None:
    repository = InMemoryConversationRepository()
    app_one = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})

    async with AsyncClient(transport=ASGITransport(app=app_one), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={"input": AMBIGUOUS, "context": {}, "conversation_id": "default"},
        )
        assert response.status_code == 200

    app_two = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})
    async with AsyncClient(transport=ASGITransport(app=app_two), base_url="http://test") as client:
        approvals = await client.get("/api/v1/approvals")
        assert approvals.status_code == 200
        payload = approvals.json()
        assert len(payload) == 1
        assert payload[0]["message_type"] == "approval_request"
        assert payload[0]["metadata"]["status"] == "pending"


@pytest.mark.anyio
async def test_running_tasks_are_marked_interrupted_on_restart() -> None:
    repository = InMemoryConversationRepository()
    task_repository = InMemoryTaskRepository()
    task_id = "00000000-0000-0000-0000-000000000111"

    app_one = create_employee_app(
        "arthur",
        {
            "org_id": "org-1",
            "conversation_repository": repository,
            "task_repository": task_repository,
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app_one), base_url="http://test") as client:
        pending_request = client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "input": CLEAR_QUALIFIED,
                "context": {"_test_runtime_delay_seconds": 10},
                "conversation_id": "default",
            },
            timeout=None,
        )
        request_task = asyncio.create_task(pending_request)
        try:
            for _ in range(20):
                response = await client.get(f"/api/v1/tasks/{task_id}")
                if response.status_code == 200 and response.json()["status"] == "running":
                    break
                await asyncio.sleep(0.1)
            else:
                raise AssertionError("task never entered running state")
        finally:
            request_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await request_task

    app_two = create_employee_app(
        "arthur",
        {
            "org_id": "org-1",
            "conversation_repository": repository,
            "task_repository": task_repository,
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app_two), base_url="http://test") as client:
        task_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert task_response.status_code == 200
        assert task_response.json()["status"] == "interrupted"
        assert task_response.json()["interruption_reason"] == "runtime_restarted_before_task_completion"

        recovery = await client.get("/api/v1/runtime/recovery")
        assert recovery.status_code == 200
        assert task_id in recovery.json()["startup_summary"]["interrupted_task_ids"]

        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert any(message["message_type"] == "status_update" and message["metadata"].get("recovery") for message in messages)


@pytest.mark.anyio
async def test_corrections_and_daily_loop_messages_persist_after_restart() -> None:
    repository = InMemoryConversationRepository()

    legal_app = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})
    async with AsyncClient(transport=ASGITransport(app=legal_app), base_url="http://test") as client:
        task = await client.post(
            "/api/v1/tasks",
            json={"input": CLEAR_QUALIFIED, "context": {}, "conversation_id": "default"},
        )
        assert task.status_code == 200
        task_id = task.json()["task_id"]
        correction = await client.post(
            f"/api/v1/tasks/{task_id}/corrections",
            json={"message": "You misread the incident date.", "corrected_output": "Use February 15, 2026."},
        )
        assert correction.status_code == 200

    exec_repository = InMemoryConversationRepository()
    exec_app_one = create_employee_app(
        "avery",
        {
            "manifest": _executive_manifest(),
            "supervisor_email": "ceo@example.com",
            "conversation_repository": exec_repository,
            "email_fixtures": [
                {
                    "id": "msg-1",
                    "from": "sarah@example.com",
                    "subject": "Planning",
                    "body": "Please schedule a meeting next week and draft a follow-up.",
                    "read": False,
                }
            ],
        },
    )
    async with AsyncClient(transport=ASGITransport(app=exec_app_one), base_url="http://test") as client:
        daily_loop = await client.post("/api/v1/autonomy/daily-loop", json={"conversation_id": "default", "max_items": 3})
        assert daily_loop.status_code == 200

    legal_app_two = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})
    async with AsyncClient(transport=ASGITransport(app=legal_app_two), base_url="http://test") as client:
        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200
        contents = [message["content"] for message in history.json()["messages"]]
        assert any("You're right. I misread that. Correcting now." in content for content in contents)

    exec_app_two = create_employee_app(
        "avery",
        {
            "manifest": _executive_manifest(),
            "supervisor_email": "ceo@example.com",
            "conversation_repository": exec_repository,
        },
    )
    async with AsyncClient(transport=ASGITransport(app=exec_app_two), base_url="http://test") as client:
        history = await client.get("/api/v1/chat/history")
        assert history.status_code == 200
        contents = [message["content"] for message in history.json()["messages"]]
        assert any("Morning briefing from Avery" in content for content in contents)
        assert any("Wind-down summary" in content for content in contents)


def test_websocket_chat_persists_messages_in_order() -> None:
    repository = InMemoryConversationRepository()
    app = create_employee_app("arthur", {"org_id": "org-1", "conversation_repository": repository})

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "chat_message",
                    "conversation_id": "default",
                    "content": CLEAR_QUALIFIED,
                }
            )
            while True:
                message = websocket.receive_json()
                if message["type"] == "complete":
                    break

        history = client.get("/api/v1/chat/history")
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == CLEAR_QUALIFIED
        assert messages[-1]["message_type"] == "status_update"


@pytest.mark.anyio
async def test_runtime_health_degrades_when_employee_local_db_fails() -> None:
    app = create_employee_app(
        "arthur",
        {
            "org_id": "org-1",
            "employee_database_url": "sqlite+aiosqlite:///:memory:",
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 503
        assert health.json()["status"] == "degraded"

        task = await client.post(
            "/api/v1/tasks",
            json={"input": CLEAR_QUALIFIED, "context": {}, "conversation_id": "default"},
        )
        assert task.status_code == 503
