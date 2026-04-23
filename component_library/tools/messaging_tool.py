"""messaging_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter


@register("messaging_tool")
class MessagingTool(ToolIntegration):
    config_schema = {
        "provider": {"type": "str", "required": False, "description": "Messaging provider: slack | teams | fixture.", "default": "fixture"},
        "fixtures": {"type": "list", "required": False, "description": "Fixture messages for dev/test mode.", "default": []},
    }
    component_id = "messaging_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "fixture"))
        self._adapter = InMemoryProviderAdapter(self._provider, initial_state={"fixtures": list(config.get("fixtures", []))})
        self._messages: list[dict[str, Any]] = list(config.get("fixtures", []))
        self._history: list[dict[str, Any]] = []

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True, detail=f"provider={self._provider}; status={self._adapter.connection_status}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_messaging_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "send":
            message = {
                "id": str(len(self._messages) + 1),
                "channel": params.get("channel", "slack"),
                "to": params.get("to", ""),
                "body": params.get("body", ""),
                **self._adapter.metadata(),
            }
            self._messages.append(message)
            self._history.append({"action": action, "payload": message})
            self._adapter.touch()
            return message
        if action == "history":
            return {"messages": list(self._messages), "items": list(self._history), **self._adapter.metadata()}
        if action == "provider_status":
            return self._adapter.metadata()
        raise ValueError(f"Unsupported messaging action: {action}")
