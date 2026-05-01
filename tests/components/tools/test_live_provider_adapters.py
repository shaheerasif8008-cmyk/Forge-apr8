from __future__ import annotations

from typing import Any

import pytest

from component_library.interfaces import ComponentInitializationError
from component_library.tools.calendar_tool import CalendarTool
from component_library.tools.crm_tool import CrmTool
from component_library.tools.email_tool import EmailTool
from component_library.tools.messaging_tool import MessagingTool


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_cls", "provider", "action", "params"),
    [
        (
            EmailTool,
            "gmail",
            "send",
            {"to": "ops@example.com", "subject": "Close", "body": "Done"},
        ),
        (
            CalendarTool,
            "outlook",
            "create_event",
            {"title": "Review", "time": "2026-05-01T15:00:00Z", "attendees": ["ops@example.com"]},
        ),
        (
            MessagingTool,
            "slack",
            "send",
            {"channel": "finance", "to": "#finance", "body": "Approved"},
        ),
        (
            CrmTool,
            "hubspot",
            "upsert_contact",
            {"email": "buyer@example.com", "name": "Buyer"},
        ),
    ],
)
async def test_live_provider_mode_posts_composio_action_payload(
    tool_cls: type[EmailTool] | type[CalendarTool] | type[MessagingTool] | type[CrmTool],
    provider: str,
    action: str,
    params: dict[str, Any],
) -> None:
    calls: list[dict[str, Any]] = []

    async def transport(request: dict[str, Any]) -> dict[str, Any]:
        calls.append(request)
        return {"ok": True, "external_id": "composio-1"}

    tool = tool_cls()
    await tool.initialize(
        {
            "provider": provider,
            "composio_api_key": "test-key",
            "action_slugs": {action: f"{provider.upper()}_{action.upper()}"},
            "connected_account_id": "conn-123",
            "user_id": "user-123",
            "http_transport": transport,
        }
    )

    result = await tool.invoke(action, params)
    health = await tool.health_check()

    assert calls == [
        {
            "url": f"https://backend.composio.dev/api/v3.1/tools/execute/{provider.upper()}_{action.upper()}",
            "provider": provider,
            "action": action,
            "tool_slug": f"{provider.upper()}_{action.upper()}",
            "body": {
                "arguments": params,
                "connected_account_id": "conn-123",
                "user_id": "user-123",
            },
            "headers": {"x-api-key": "test-key"},
        }
    ]
    assert result["provider"] == provider
    assert result["adapter_mode"] == "live"
    assert result["response"] == {"ok": True, "external_id": "composio-1"}
    assert health.healthy is True
    assert f"provider={provider}" in health.detail
    assert "mode=live" in health.detail


@pytest.mark.anyio
async def test_strict_live_provider_requires_composio_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    tool = MessagingTool()

    with pytest.raises(ComponentInitializationError, match="slack.*COMPOSIO_API_KEY"):
        await tool.initialize({"provider": "slack", "strict_provider": True})


@pytest.mark.anyio
async def test_fixture_mode_remains_stateful_without_live_credentials() -> None:
    tool = EmailTool()
    await tool.initialize(
        {
            "provider": "fixture",
            "fixtures": [{"id": "1", "subject": "Hello", "read": False}],
        }
    )

    sent = await tool.invoke("send", {"to": "user@example.com", "subject": "Test", "body": "Hi"})
    updated = await tool.invoke("mark_read", {"message_id": "1"})
    health = await tool.health_check()

    assert sent["status"] == "sent"
    assert sent["provider"] == "fixture"
    assert sent["adapter_mode"] == "fixture"
    assert updated["read"] is True
    assert health.healthy is True
    assert "mode=fixture" in health.detail


@pytest.mark.anyio
async def test_non_strict_live_provider_without_credentials_reports_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    tool = CrmTool()
    await tool.initialize({"provider": "salesforce"})

    result = await tool.invoke("upsert_contact", {"email": "lead@example.com"})
    health = await tool.health_check()

    assert result["provider"] == "salesforce"
    assert result["adapter_mode"] == "fallback_missing_credentials"
    assert result["record"] == {"email": "lead@example.com"}
    assert health.healthy is False
    assert "mode=fallback_missing_credentials" in health.detail
