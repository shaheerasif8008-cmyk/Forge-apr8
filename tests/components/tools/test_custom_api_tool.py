from __future__ import annotations

import httpx
import pytest

from component_library.tools.custom_api_tool import CustomApiTool


@pytest.mark.anyio
async def test_custom_api_tool_bearer_get() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token-123"
        return httpx.Response(200, json={"ok": True})

    tool = CustomApiTool()
    await tool.initialize(
        {
            "base_url": "https://api.example.com",
            "auth_type": "bearer",
            "auth_config": {"token": "token-123"},
            "transport": httpx.MockTransport(_handler),
        }
    )
    result = await tool.invoke("get", {"path": "/status"})
    assert result["json"] == {"ok": True}


@pytest.mark.anyio
async def test_custom_api_tool_retries_rate_limit() -> None:
    calls = {"count": 0}

    async def _handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"items": [{"id": 1}]})

    tool = CustomApiTool()
    await tool.initialize(
        {
            "base_url": "https://api.example.com",
            "transport": httpx.MockTransport(_handler),
            "max_retries": 1,
        }
    )
    result = await tool.invoke("get", {"path": "/items"})
    assert result["json"] == {"items": [{"id": 1}]}
    assert calls["count"] == 2


@pytest.mark.anyio
async def test_custom_api_tool_surfaces_error_payload() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    tool = CustomApiTool()
    await tool.initialize(
        {
            "base_url": "https://api.example.com",
            "transport": httpx.MockTransport(_handler),
        }
    )
    result = await tool.invoke("get", {"path": "/secure"})
    assert result["status_code"] == 401
    assert "unauthorized" in result["error"]


@pytest.mark.anyio
async def test_custom_api_tool_rejects_unknown_action() -> None:
    tool = CustomApiTool()
    await tool.initialize({"base_url": "https://api.example.com"})
    with pytest.raises(ValueError, match="Unsupported custom API action"):
        await tool.invoke("patch", {"path": "/x"})
