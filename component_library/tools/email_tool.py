"""email_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter


@register("email_tool")
class EmailTool(ToolIntegration):
    component_id = "email_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "fixture"))
        self._adapter = InMemoryProviderAdapter(
            self._provider,
            initial_state={"fixtures": list(config.get("fixtures", []))},
        )
        self._sent_messages: list[dict[str, Any]] = []
        self._inbox_messages: list[dict[str, Any]] = list(config.get("fixtures", []))
        self._history: list[dict[str, Any]] = []

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(
            healthy=True,
            detail=f"provider={self._provider}; status={self._adapter.connection_status}",
        )

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
                **self._adapter.metadata(),
            }
            self._sent_messages.append(message)
            self._history.append({"action": action, "payload": message})
            self._adapter.touch()
            return message
        if action == "check_inbox":
            criteria = str(params.get("criteria", "")).lower()
            self._adapter.touch()
            if not criteria:
                return {"messages": self._inbox_messages, **self._adapter.metadata()}
            return {
                "messages": [
                    message
                    for message in self._inbox_messages
                    if criteria in str(message).lower()
                ],
                **self._adapter.metadata(),
            }
        if action == "mark_read":
            message_id = str(params["message_id"])
            for message in self._inbox_messages:
                if str(message.get("id")) == message_id:
                    message["read"] = True
                    updated = {**message, **self._adapter.metadata()}
                    self._history.append({"action": action, "payload": updated})
                    self._adapter.touch()
                    return updated
            return {"id": message_id, "updated": False, **self._adapter.metadata()}
        if action == "provider_status":
            return self._adapter.metadata()
        if action == "history":
            return {"items": list(self._history), **self._adapter.metadata()}
        raise ValueError(f"Unsupported email action: {action}")
