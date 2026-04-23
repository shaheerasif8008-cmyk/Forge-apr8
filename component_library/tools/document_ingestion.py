"""document_ingestion integration component."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

from component_library.interfaces import (
    ComponentHealth,
    ComponentInitializationError,
    ToolIntegration,
    strict_providers_enabled,
)
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter

try:  # pragma: no cover - optional dependency
    from unstructured.partition.auto import partition
except Exception:  # pragma: no cover - optional dependency
    partition = None

logger = structlog.get_logger(__name__)


@register("document_ingestion")
class DocumentIngestion(ToolIntegration):
    config_schema = {
        "provider": {"type": "str", "required": False, "description": "Parsing backend: unstructured | local (naive text split).", "default": "local"},
    }
    component_id = "document_ingestion"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "local"))
        self._adapter = InMemoryProviderAdapter(self._provider)
        self._fallback_active = partition is None
        if self._fallback_active:
            logger.warning(
                "component_fallback_active",
                component="document_ingestion",
                reason="unstructured not installed; using naive text splitting",
            )
            if strict_providers_enabled():
                raise ComponentInitializationError(
                    "document_ingestion: unstructured required when FORGE_STRICT_PROVIDERS=true. "
                    "Install with: pip install 'unstructured[all-docs]'"
                )

    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(
                healthy=False,
                detail="fallback_mode: unstructured not installed; using naive text split",
            )
        mode = "unstructured" if partition is not None else "fallback"
        return ComponentHealth(healthy=True, detail=f"provider={self._provider}; mode={mode}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_document_ingestion.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "parse":
            return await self._parse(params)
        if action == "chunk":
            return await self._chunk(params)
        if action == "extract_text":
            return await self._extract_text(params)
        raise ValueError(f"Unsupported document ingestion action: {action}")

    async def _parse(self, params: dict[str, Any]) -> dict[str, Any]:
        if partition is not None and params.get("file_path"):
            elements = partition(filename=str(params["file_path"]))
            parsed = [
                {
                    "type": getattr(element, "category", "element"),
                    "text": str(element),
                }
                for element in elements
                if str(element).strip()
            ]
        else:
            raw_text = self._resolve_raw_text(params)
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw_text) if part.strip()]
            parsed = [{"type": "paragraph", "text": self._normalize_text(paragraph)} for paragraph in paragraphs] or [
                {"type": "paragraph", "text": self._normalize_text(raw_text)}
            ]
        self._adapter.touch()
        return {"elements": parsed, **self._adapter.metadata()}

    async def _chunk(self, params: dict[str, Any]) -> dict[str, Any]:
        elements = params.get("elements")
        if not elements:
            elements = (await self._parse(params)).get("elements", [])
        max_chunk_size = int(params.get("max_chunk_size", 500))
        chunks: list[dict[str, Any]] = []
        current = ""
        for element in elements:
            text = str(element.get("text", "")).strip()
            if not text:
                continue
            candidate = f"{current}\n{text}".strip() if current else text
            if len(candidate) > max_chunk_size and current:
                chunks.append({"content": current, "length": len(current)})
                current = text
            else:
                current = candidate
        if current:
            chunks.append({"content": current, "length": len(current)})
        self._adapter.touch()
        return {"chunks": chunks, **self._adapter.metadata()}

    async def _extract_text(self, params: dict[str, Any]) -> dict[str, Any]:
        text = self._resolve_text(params)
        self._adapter.touch()
        return {"text": text, **self._adapter.metadata()}

    def _resolve_raw_text(self, params: dict[str, Any]) -> str:
        if "content" in params:
            value = params["content"]
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        if "bytes" in params:
            return bytes(params["bytes"]).decode("utf-8", errors="replace")
        file_path = params.get("file_path")
        if file_path:
            return Path(str(file_path)).read_text(encoding="utf-8", errors="replace")
        return ""

    def _resolve_text(self, params: dict[str, Any]) -> str:
        return self._normalize_text(self._resolve_raw_text(params))

    def _normalize_text(self, value: Any) -> str:
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
