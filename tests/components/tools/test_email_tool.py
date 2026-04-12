from __future__ import annotations

import pytest

from component_library.tools.email_tool import EmailTool


@pytest.mark.anyio
async def test_email_tool_send_and_mark_read() -> None:
    tool = EmailTool()
    await tool.initialize({"provider": "sandbox", "fixtures": [{"id": "1", "subject": "Hello", "read": False}]})
    sent = await tool.invoke("send", {"to": "user@example.com", "subject": "Test", "body": "Hi"})
    updated = await tool.invoke("mark_read", {"message_id": "1"})
    status = await tool.invoke("provider_status", {})
    history = await tool.invoke("history", {})
    assert sent["status"] == "sent"
    assert sent["provider"] == "sandbox"
    assert updated["read"] is True
    assert status["provider"] == "sandbox"
    assert len(history["items"]) == 2
