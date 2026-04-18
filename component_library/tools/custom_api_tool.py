"""custom_api_tool integration component."""

from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx
import structlog

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter

logger = structlog.get_logger(__name__)


@register("custom_api_tool")
class CustomApiTool(ToolIntegration):
    component_id = "custom_api_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "http"))
        self._base_url = str(config.get("base_url", "")).rstrip("/")
        self._auth_type = str(config.get("auth_type", "none"))
        self._auth_config = dict(config.get("auth_config", {}))
        self._timeout = float(config.get("timeout", 20.0))
        self._max_retries = int(config.get("max_retries", 2))
        self._transport = config.get("transport")
        self._adapter = InMemoryProviderAdapter(self._provider)

    async def health_check(self) -> ComponentHealth:
        healthy = bool(self._base_url)
        return ComponentHealth(healthy=healthy, detail=f"base_url={self._base_url or 'unset'}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_custom_api_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        method = action.lower()
        if method not in {"get", "post", "put", "delete"}:
            raise ValueError(f"Unsupported custom API action: {action}")
        response = await self._request(method.upper(), params)
        self._adapter.touch()
        return response

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        path = str(params.get("path", "")).strip()
        url = path if path.startswith("http") else f"{self._base_url}{path}"
        headers = self._build_headers(params.get("headers", {}))
        query = dict(params.get("params", {}))
        json_payload = params.get("json")
        data_payload = params.get("data")

        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            for attempt in range(self._max_retries + 1):
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=query,
                    json=json_payload,
                    data=data_payload,
                )
                if response.status_code == 429 and attempt < self._max_retries:
                    retry_after = float(response.headers.get("Retry-After", "0.1"))
                    await asyncio.sleep(retry_after)
                    continue
                if response.status_code >= 500 and attempt < self._max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                break

        payload: dict[str, Any] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            **self._adapter.metadata(),
        }
        try:
            payload["json"] = response.json()
        except Exception:
            payload["json"] = None
            payload["text"] = response.text
        if response.status_code >= 400:
            payload["error"] = response.text
        return payload

    def _build_headers(self, request_headers: dict[str, Any]) -> dict[str, str]:
        headers = {str(key): str(value) for key, value in request_headers.items()}
        if self._auth_type == "bearer":
            token = self._auth_config.get("token", "")
            headers.setdefault("Authorization", f"Bearer {token}")
        elif self._auth_type == "basic":
            username = str(self._auth_config.get("username", ""))
            password = str(self._auth_config.get("password", ""))
            raw = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            headers.setdefault("Authorization", f"Basic {raw}")
        elif self._auth_type == "apikey":
            header_name = str(self._auth_config.get("header_name", "X-API-Key"))
            headers.setdefault(header_name, str(self._auth_config.get("api_key", "")))
        return headers
