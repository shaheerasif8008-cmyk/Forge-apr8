"""search_tool integration component."""

from __future__ import annotations

import os
import re
import time
from typing import Any

import anyio
import httpx
import structlog

from component_library.interfaces import ComponentHealth, ToolIntegration
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter

logger = structlog.get_logger(__name__)


@register("search_tool")
class SearchTool(ToolIntegration):
    component_id = "search_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "fixture"))
        self._api_key = str(config.get("tavily_api_key") or os.getenv("TAVILY_API_KEY") or "")
        self._fixtures = list(config.get("fixtures", []))
        self._max_results = int(config.get("max_results", 5))
        self._rate_limit_seconds = float(config.get("rate_limit_seconds", 0.0))
        self._transport = config.get("transport")
        self._timeout = float(config.get("timeout", 20.0))
        self._last_call_at = 0.0
        self._adapter = InMemoryProviderAdapter(self._provider, initial_state={"fixtures": self._fixtures})

    async def health_check(self) -> ComponentHealth:
        mode = "tavily" if self._api_key else "fixture"
        return ComponentHealth(healthy=True, detail=f"provider={self._provider}; mode={mode}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_search_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action != "search":
            raise ValueError(f"Unsupported search action: {action}")

        query = str(params.get("query", "")).strip()
        if not query:
            return {"results": [], **self._adapter.metadata()}

        max_results = int(params.get("max_results", self._max_results))
        results = await self._search(query, max_results)
        self._adapter.touch()
        return {"results": results[:max_results], **self._adapter.metadata()}

    async def _search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        if self._rate_limit_seconds > 0:
            elapsed = time.monotonic() - self._last_call_at
            if elapsed < self._rate_limit_seconds:
                await self._sleep(self._rate_limit_seconds - elapsed)

        if self._api_key:
            try:
                results = await self._search_tavily(query, max_results)
                self._last_call_at = time.monotonic()
                return results
            except Exception as exc:
                logger.warning("search_tool_remote_failed", error=str(exc))

        self._last_call_at = time.monotonic()
        return self._search_fixtures(query, max_results)

    async def _search_tavily(self, query: str, max_results: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                },
            )
            response.raise_for_status()
            payload = response.json()
        return [
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
            }
            for item in payload.get("results", [])
        ]

    def _search_fixtures(self, query: str, max_results: int) -> list[dict[str, Any]]:
        tokens = [token for token in re.findall(r"[a-zA-Z0-9]+", query.lower()) if token]
        scored: list[tuple[int, dict[str, Any]]] = []
        for fixture in self._fixtures:
            haystack = " ".join(
                str(fixture.get(key, ""))
                for key in ("title", "content", "snippet", "url")
            ).lower()
            score = sum(token in haystack for token in tokens)
            if score or not tokens:
                scored.append(
                    (
                        score,
                        {
                            "url": fixture.get("url", ""),
                            "title": fixture.get("title", ""),
                            "snippet": fixture.get("content", fixture.get("snippet", "")),
                        },
                    )
                )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [result for _, result in scored[:max_results]]

    async def _sleep(self, duration: float) -> None:
        if duration <= 0:
            return
        await anyio.sleep(duration)
