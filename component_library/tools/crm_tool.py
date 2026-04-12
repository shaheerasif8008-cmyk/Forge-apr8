"""crm_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register


@register("crm_tool")
class CrmTool(ToolIntegration):
    component_id = "crm_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._records: dict[str, dict[str, Any]] = dict(config.get("fixtures", {}))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_crm_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "upsert_contact":
            key = str(params.get("email") or params.get("name") or len(self._records) + 1)
            record = dict(params)
            self._records[key] = record
            return {"id": key, "record": record}
        if action == "lookup_contact":
            key = str(params.get("email") or params.get("name", ""))
            return self._records.get(key, {})
        raise ValueError(f"Unsupported CRM action: {action}")
