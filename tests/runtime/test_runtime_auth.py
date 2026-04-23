from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


@pytest.mark.anyio
async def test_runtime_requires_bearer_token_when_configured() -> None:
    app = create_employee_app(
        "secure-employee",
        {
            "org_id": "org-1",
            "auth_required": True,
            "api_auth_token": "runtime-token",
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get("/api/v1/chat/history")
        assert unauthorized.status_code == 401

        authorized = await client.get(
            "/api/v1/chat/history",
            headers={"Authorization": "Bearer runtime-token"},
        )
        assert authorized.status_code == 200


@pytest.mark.anyio
async def test_runtime_uses_employee_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMPLOYEE_API_KEY", "env-runtime-token")
    app = create_employee_app("env-secure-employee", {"org_id": "org-1"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/v1/health")
        assert health.status_code == 200

        unauthorized = await client.get("/api/v1/chat/history")
        assert unauthorized.status_code == 401

        authorized = await client.get(
            "/api/v1/chat/history",
            headers={"Authorization": "Bearer env-runtime-token"},
        )
        assert authorized.status_code == 200
