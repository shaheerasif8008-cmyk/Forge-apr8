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


class WorkCapability(BaseComponent):
    """Base class for category-2 work capability components."""

    category = "work"

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """Execute the work capability with typed input/output."""


class ToolIntegration(BaseComponent):
    """Base class for category-3 tool integrations."""

    category = "tools"

    @abstractmethod
    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool action and return a structured result."""


class DataSource(BaseComponent):
    """Base class for category-4 data sources."""

    category = "data"

    @abstractmethod
    async def query(self, query: str, **kwargs: Any) -> Any:
        """Run a source-specific query."""


class QualityModule(BaseComponent):
    """Base class for category-5 quality and governance components."""

    category = "quality"

    @abstractmethod
    async def evaluate(self, input_data: Any) -> BaseModel:
        """Evaluate some input and return a structured assessment."""
