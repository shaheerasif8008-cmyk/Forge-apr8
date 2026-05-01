"""crm_tool integration component — connects to external system via Composio."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import build_provider_adapter, is_live_adapter, is_provider_fallback


@register("crm_tool")
class CrmTool(ToolIntegration):
    config_schema = {
        "provider": {"type": "str", "required": False, "description": "CRM provider: salesforce | hubspot | fixture.", "default": "fixture"},
        "composio_api_key": {"type": "str", "required": False, "description": "Composio API key for Salesforce/HubSpot integration.", "default": ""},
        "strict_provider": {"type": "bool", "required": False, "description": "Fail initialization if a live provider lacks credentials.", "default": False},
        "fixtures": {"type": "dict", "required": False, "description": "Fixture CRM records keyed by email/name for dev/test mode.", "default": {}},
    }
    component_id = "crm_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "fixture")).strip().lower() or "fixture"
        self._adapter = build_provider_adapter(
            self._provider,
            config,
            initial_state={"fixtures": dict(config.get("fixtures", {}))},
        )
        self._records: dict[str, dict[str, Any]] = dict(config.get("fixtures", {}))
        self._history: list[dict[str, Any]] = []

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(
            healthy=not is_provider_fallback(self._adapter),
            detail=(
                f"provider={self._provider}; mode={self._adapter.adapter_mode}; "
                f"status={self._adapter.connection_status}"
            ),
        )

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_crm_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if is_live_adapter(self._adapter) and action not in {"provider_status", "history"}:
            result = await self._adapter.invoke(action, params)
            self._history.append({"action": action, "payload": result})
            return result
        if action == "upsert_contact":
            key = str(params.get("email") or params.get("name") or len(self._records) + 1)
            record = dict(params)
            self._records[key] = record
            payload = {"id": key, "record": record, **self._adapter.metadata()}
            self._history.append({"action": action, "payload": payload})
            self._adapter.touch()
            return payload
        if action == "lookup_contact":
            key = str(params.get("email") or params.get("name", ""))
            self._adapter.touch()
            return {"record": self._records.get(key, {}), **self._adapter.metadata()}
        if action == "provider_status":
            return self._adapter.metadata()
        if action == "history":
            return {"items": list(self._history), **self._adapter.metadata()}
        raise ValueError(f"Unsupported CRM action: {action}")
