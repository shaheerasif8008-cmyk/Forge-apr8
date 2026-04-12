"""calendar_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter


@register("calendar_tool")
class CalendarTool(ToolIntegration):
    component_id = "calendar_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "fixture"))
        self._adapter = InMemoryProviderAdapter(self._provider, initial_state={"fixtures": list(config.get("fixtures", []))})
        self._events: list[dict[str, Any]] = list(config.get("fixtures", []))
        self._history: list[dict[str, Any]] = []

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True, detail=f"provider={self._provider}; status={self._adapter.connection_status}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_calendar_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "create_event":
            event = {
                "id": str(len(self._events) + 1),
                "title": params.get("title", "Untitled event"),
                "time": params.get("time", ""),
                "attendees": params.get("attendees", []),
                **self._adapter.metadata(),
            }
            self._events.append(event)
            self._history.append({"action": action, "payload": event})
            self._adapter.touch()
            return event
        if action == "list_events":
            self._adapter.touch()
            return {"events": list(self._events), **self._adapter.metadata()}
        if action == "provider_status":
            return self._adapter.metadata()
        if action == "history":
            return {"items": list(self._history), **self._adapter.metadata()}
        raise ValueError(f"Unsupported calendar action: {action}")
