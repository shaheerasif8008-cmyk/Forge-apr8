"""calendar_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register


@register("calendar_tool")
class CalendarTool(ToolIntegration):
    component_id = "calendar_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._events: list[dict[str, Any]] = list(config.get("fixtures", []))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_calendar_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "create_event":
            event = {
                "id": str(len(self._events) + 1),
                "title": params.get("title", "Untitled event"),
                "time": params.get("time", ""),
                "attendees": params.get("attendees", []),
            }
            self._events.append(event)
            return event
        if action == "list_events":
            return {"events": list(self._events)}
        raise ValueError(f"Unsupported calendar action: {action}")
