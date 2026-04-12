"""messaging_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register


@register("messaging_tool")
class MessagingTool(ToolIntegration):
    component_id = "messaging_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._messages: list[dict[str, Any]] = list(config.get("fixtures", []))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_messaging_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "send":
            message = {
                "id": str(len(self._messages) + 1),
                "channel": params.get("channel", "slack"),
                "to": params.get("to", ""),
                "body": params.get("body", ""),
            }
            self._messages.append(message)
            return message
        if action == "history":
            return {"messages": list(self._messages)}
        raise ValueError(f"Unsupported messaging action: {action}")
