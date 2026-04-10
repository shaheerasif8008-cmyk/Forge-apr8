"""litellm multi-model router component."""

from __future__ import annotations

from typing import Any

import structlog

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register

logger = structlog.get_logger(__name__)


@register("litellm_router")
class LitellmRouter(BaseComponent):
    """Routes LLM calls across providers with fallback support."""

    component_id = "litellm_router"
    version = "1.0.0"
    category = "models"

    _primary: str = ""
    _fallback: str = ""

    async def initialize(self, config: dict[str, Any]) -> None:
        self._primary = config.get("primary_model", "")
        self._fallback = config.get("fallback_model", "")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=bool(self._primary), detail=f"primary={self._primary}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/models/test_litellm_router.py"]
