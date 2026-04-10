"""Anthropic model provider component."""

from __future__ import annotations

from typing import Any

import structlog

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register

logger = structlog.get_logger(__name__)


@register("anthropic_provider")
class AnthropicProvider(BaseComponent):
    """Routes calls to Anthropic Claude via litellm."""

    component_id = "anthropic_provider"
    version = "1.0.0"
    category = "models"

    _model: str = "claude-3-5-sonnet-20241022"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._model = config.get("model", self._model)
        logger.info("anthropic_provider_init", model=self._model)

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True, detail=f"model={self._model}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/models/test_anthropic_provider.py"]
