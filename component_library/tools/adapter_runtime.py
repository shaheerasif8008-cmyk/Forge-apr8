"""Shared provider adapter helpers for runtime tool integrations."""

from __future__ import annotations

import inspect
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib import request

from component_library.interfaces import ComponentInitializationError, strict_providers_enabled


COMPOSIO_API_BASE = "https://backend.composio.dev/api/v3.1"
LIVE_COMPOSIO_PROVIDERS = frozenset(
    {
        "gmail",
        "google",
        "outlook",
        "slack",
        "teams",
        "hubspot",
        "salesforce",
    }
)
HTTPTransport = Callable[[dict[str, Any]], Any]


class InMemoryProviderAdapter:
    """Stateful provider adapter for local, sandbox, and fixture-backed integrations."""

    def __init__(
        self,
        provider: str,
        *,
        initial_state: dict[str, Any] | None = None,
        adapter_mode: str = "fixture",
        connection_status: str = "ready",
    ) -> None:
        self.provider = provider
        self.initial_state = initial_state or {}
        self.adapter_mode = adapter_mode
        self.connection_status = connection_status
        self.last_synced_at = datetime.now(UTC).isoformat()

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "adapter_mode": self.adapter_mode,
            "connection_status": self.connection_status,
            "last_synced_at": self.last_synced_at,
        }

    def touch(self) -> None:
        self.last_synced_at = datetime.now(UTC).isoformat()


class ComposioProviderAdapter:
    """HTTP-backed adapter for Composio-style provider actions."""

    adapter_mode = "live"
    connection_status = "ready"

    def __init__(
        self,
        provider: str,
        *,
        api_key: str,
        base_url: str = COMPOSIO_API_BASE,
        action_slugs: dict[str, str] | None = None,
        connected_account_id: str = "",
        user_id: str = "",
        transport: HTTPTransport | None = None,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.action_slugs = action_slugs or {}
        self.connected_account_id = connected_account_id
        self.user_id = user_id
        self.transport = transport or _default_http_transport
        self.last_synced_at = datetime.now(UTC).isoformat()

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "adapter_mode": self.adapter_mode,
            "connection_status": self.connection_status,
            "last_synced_at": self.last_synced_at,
        }

    def touch(self) -> None:
        self.last_synced_at = datetime.now(UTC).isoformat()

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        tool_slug = self._tool_slug(action)
        body: dict[str, Any] = {"arguments": params}
        if self.connected_account_id:
            body["connected_account_id"] = self.connected_account_id
        if self.user_id:
            body["user_id"] = self.user_id
        request_payload = {
            "url": f"{self.base_url.rstrip('/')}/tools/execute/{tool_slug}",
            "provider": self.provider,
            "action": action,
            "tool_slug": tool_slug,
            "body": body,
            "headers": {"x-api-key": self.api_key},
        }
        response = self.transport(request_payload)
        if inspect.isawaitable(response):
            response = await response
        self.touch()
        return {
            "action": action,
            "params": params,
            "response": response,
            **self.metadata(),
        }

    def _tool_slug(self, action: str) -> str:
        configured = self.action_slugs.get(action) or self.action_slugs.get(action.lower())
        if configured:
            return configured
        return f"{self.provider}_{action}".upper()


def build_provider_adapter(
    provider: str,
    config: dict[str, Any],
    *,
    initial_state: dict[str, Any] | None = None,
) -> InMemoryProviderAdapter | ComposioProviderAdapter:
    normalized_provider = provider.strip().lower() or "fixture"
    api_key = str(config.get("composio_api_key") or os.environ.get("COMPOSIO_API_KEY") or "").strip()
    strict = _truthy(config.get("strict_provider")) or strict_providers_enabled()
    if normalized_provider in LIVE_COMPOSIO_PROVIDERS:
        if api_key:
            return ComposioProviderAdapter(
                normalized_provider,
                api_key=api_key,
                base_url=str(config.get("composio_base_url") or COMPOSIO_API_BASE),
                action_slugs=dict(config.get("action_slugs", {})),
                connected_account_id=str(config.get("connected_account_id", "")),
                user_id=str(config.get("user_id", "")),
                transport=config.get("http_transport"),
            )
        if strict:
            raise ComponentInitializationError(
                f"Live provider {normalized_provider} requires composio_api_key or COMPOSIO_API_KEY"
            )
        return InMemoryProviderAdapter(
            normalized_provider,
            initial_state=initial_state,
            adapter_mode="fallback_missing_credentials",
            connection_status="fixture_fallback",
        )
    return InMemoryProviderAdapter(
        normalized_provider,
        initial_state=initial_state,
        adapter_mode="fixture",
    )


def is_live_adapter(adapter: InMemoryProviderAdapter | ComposioProviderAdapter) -> bool:
    return adapter.adapter_mode == "live"


def is_provider_fallback(adapter: InMemoryProviderAdapter | ComposioProviderAdapter) -> bool:
    return adapter.adapter_mode.startswith("fallback_")


def _default_http_transport(request_payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(request_payload["body"]).encode("utf-8")
    http_request = request.Request(
        str(request_payload["url"]),
        data=body,
        headers={
            **request_payload["headers"],
            "content-type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(http_request, timeout=30) as response:
        response_body = response.read().decode("utf-8")
    if not response_body:
        return {}
    return json.loads(response_body)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
