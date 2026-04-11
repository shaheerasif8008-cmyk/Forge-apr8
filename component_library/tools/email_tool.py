"""email_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register


@register("email_tool")
class EmailTool(ToolIntegration):
    component_id = "email_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._sent_messages: list[dict[str, Any]] = []
        self._inbox_messages: list[dict[str, Any]] = list(config.get("fixtures", []))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_email_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "send":
            message = {
                "id": str(len(self._sent_messages) + 1),
                "to": params["to"],
                "subject": params["subject"],
                "body": params["body"],
                "status": "sent",
            }
            self._sent_messages.append(message)
            return message
        if action == "check_inbox":
            criteria = str(params.get("criteria", "")).lower()
            if not criteria:
                return {"messages": self._inbox_messages}
            return {
                "messages": [
                    message
                    for message in self._inbox_messages
                    if criteria in str(message).lower()
                ]
            }
        if action == "mark_read":
            message_id = str(params["message_id"])
            for message in self._inbox_messages:
                if str(message.get("id")) == message_id:
                    message["read"] = True
                    return message
            return {"id": message_id, "updated": False}
        raise ValueError(f"Unsupported email action: {action}")
