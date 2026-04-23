"""monitor_scanner work capability component."""

from __future__ import annotations

import os
from typing import Any

import structlog
from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import ScanRequest, Signal

logger = structlog.get_logger(__name__)


class _SignalAssessment(BaseModel):
    relevant: bool
    raw_score: float
    rationale: str = ""
    summary: str


@register("monitor_scanner")
class MonitorScanner(WorkCapability):
    config_schema = {
        "email_tool": {"type": "object", "required": False, "description": "Email tool used when scanning inbox sources.", "default": None},
        "search_tool": {"type": "object", "required": False, "description": "Search tool used when scanning web sources.", "default": None},
        "calendar_tool": {"type": "object", "required": False, "description": "Calendar tool used when scanning event sources.", "default": None},
        "file_storage_tool": {"type": "object", "required": False, "description": "File storage tool used when scanning file sources.", "default": None},
        "custom_api_tool": {"type": "object", "required": False, "description": "Custom API tool used when scanning API sources.", "default": None},
        "model_client": {"type": "object", "required": False, "description": "Optional model client for LLM-backed signal classification.", "default": None},
        "fallback_mode": {"type": "str", "required": False, "description": "Fallback classification mode when no model client is used.", "default": "deterministic"},
        "force_llm": {"type": "bool", "required": False, "description": "Force LLM signal classification when a model client is configured.", "default": False},
    }
    component_id = "monitor_scanner"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._email_tool = config.get("email_tool")
        self._search_tool = config.get("search_tool")
        self._calendar_tool = config.get("calendar_tool")
        self._file_storage_tool = config.get("file_storage_tool")
        self._custom_api_tool = config.get("custom_api_tool")
        self._model_client = config.get("model_client")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        available = [
            name
            for name, component in (
                ("email", self._email_tool),
                ("web_feed", self._search_tool),
                ("calendar", self._calendar_tool),
                ("doc_store", self._file_storage_tool),
                ("api", self._custom_api_tool),
            )
            if component is not None
        ]
        return ComponentHealth(healthy=bool(available), detail=f"available_sources={','.join(available)}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_monitor_scanner.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ScanRequest):
            raise TypeError("MonitorScanner expects ScanRequest")
        return await self.scan(input_data)  # type: ignore[return-value]

    async def scan(self, request: ScanRequest) -> list[Signal]:
        items = request.raw_items or await self._collect_items(request)
        if not items:
            return []

        signals: list[Signal] = []
        for item in items[: request.limit]:
            assessment = await self._assess_item(request, item)
            if not assessment.relevant:
                continue
            signals.append(
                Signal(
                    source=request.source,
                    content=assessment.summary,
                    timestamp=str(item.get("timestamp") or item.get("time") or item.get("created_at") or ""),
                    raw_score=round(max(0.0, min(assessment.raw_score, 1.0)), 2),
                    metadata={
                        "rationale": assessment.rationale,
                        "item": item,
                    },
                )
            )
        logger.info("monitor_scanner_complete", source=request.source, signal_count=len(signals))
        return signals

    async def _collect_items(self, request: ScanRequest) -> list[dict[str, Any]]:
        source = request.source.strip().lower()
        if source == "email":
            if self._email_tool is None:
                return []
            payload = await self._email_tool.invoke(
                "check_inbox",
                {"criteria": request.query or " ".join(request.criteria)},
            )
            return list(payload.get("messages", []))
        if source == "web_feed":
            if self._search_tool is None:
                return []
            payload = await self._search_tool.invoke(
                "search",
                {"query": request.query or " ".join(request.criteria), "max_results": request.limit},
            )
            return list(payload.get("results", []))
        if source == "calendar":
            if self._calendar_tool is None:
                return []
            payload = await self._calendar_tool.invoke("list_events", {})
            return list(payload.get("events", []))
        if source == "doc_store":
            if self._file_storage_tool is None:
                return []
            payload = await self._file_storage_tool.invoke(
                "list",
                {"prefix": request.source_config.get("prefix", "")},
            )
            return list(payload.get("items", []))
        if source == "api":
            if self._custom_api_tool is None:
                return []
            payload = await self._custom_api_tool.invoke(
                "get",
                {"path": request.source_config.get("path", "/")},
            )
            json_payload = payload.get("json")
            if isinstance(json_payload, list):
                return [item for item in json_payload if isinstance(item, dict)]
            if isinstance(json_payload, dict):
                for key in ("items", "results", "events"):
                    value = json_payload.get(key)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
            return []
        raise ValueError(f"Unsupported signal source: {request.source}")

    async def _assess_item(self, request: ScanRequest, item: dict[str, Any]) -> _SignalAssessment:
        if self._can_use_model():
            try:
                return await self._assess_with_model(request, item)
            except Exception as exc:
                logger.warning("monitor_scanner_llm_failed", source=request.source, error=str(exc))
                if self._fallback_mode != "deterministic":
                    raise
        return self._assess_deterministic(request, item)

    async def _assess_with_model(self, request: ScanRequest, item: dict[str, Any]) -> _SignalAssessment:
        system_prompt = (
            "You classify operational signals for an autonomous employee. "
            "Return relevant=true only when the item needs attention or indicates a meaningful change."
        )
        user_message = (
            f"SOURCE: {request.source}\n"
            f"QUERY: {request.query}\n"
            f"CRITERIA: {request.criteria}\n"
            f"ITEM: {item}"
        )
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete_structured(
                TaskType.STRUCTURED,
                system_prompt,
                user_message,
                _SignalAssessment,
            )
        if hasattr(self._model_client, "complete_structured"):
            return await self._model_client.complete_structured(
                system_prompt,
                user_message,
                _SignalAssessment,
            )
        return await self._model_client.structure(
            _SignalAssessment,
            user_message,
            system_prompt=system_prompt,
        )

    def _assess_deterministic(self, request: ScanRequest, item: dict[str, Any]) -> _SignalAssessment:
        haystack = " ".join(str(value) for value in item.values()).lower()
        criteria = [token.lower() for token in request.criteria if token.strip()]
        query_tokens = [token.lower() for token in request.query.split() if token.strip()]
        tokens = list(dict.fromkeys(criteria + query_tokens))
        matches = sum(token in haystack for token in tokens)
        urgent_bonus = 1 if any(token in haystack for token in ("urgent", "deadline", "overdue", "alert")) else 0
        score = min(1.0, 0.2 + (0.18 * matches) + (0.2 * urgent_bonus))
        relevant = matches > 0 or urgent_bonus > 0 or not tokens
        content = str(
            item.get("subject")
            or item.get("title")
            or item.get("snippet")
            or item.get("content")
            or item
        )
        rationale = f"matches={matches}; urgent_bonus={urgent_bonus}"
        return _SignalAssessment(
            relevant=relevant,
            raw_score=score,
            rationale=rationale,
            summary=content[:240],
        )

    def _can_use_model(self) -> bool:
        if self._model_client is None:
            return False
        if self._config.get("force_llm"):
            return True
        client_id = getattr(self._model_client, "component_id", "")
        if client_id == "litellm_router":
            return any(
                os.getenv(name)
                for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
            )
        if client_id == "anthropic_provider":
            return bool(getattr(self._model_client, "_api_key", None) or os.getenv("ANTHROPIC_API_KEY"))
        return True
