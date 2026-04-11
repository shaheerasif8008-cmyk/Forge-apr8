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
