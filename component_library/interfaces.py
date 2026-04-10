"""Standard interfaces that every library component must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ComponentConfig(BaseModel):
    """Base configuration model for all components."""
    component_id: str
    version: str = "1.0.0"


class ComponentHealth(BaseModel):
    healthy: bool
    detail: str = ""


class BaseComponent(ABC):
    """Contract every component must satisfy."""

    component_id: str
    version: str
    category: str  # models | work | tools | data | quality

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Configure the component from a config dict."""

    @abstractmethod
    async def health_check(self) -> ComponentHealth:
        """Return current health status."""

    @abstractmethod
    def get_test_suite(self) -> list[str]:
        """Return test module paths for this component."""
