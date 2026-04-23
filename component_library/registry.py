"""Component registry — discovers and instantiates library components by ID."""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from component_library.interfaces import BaseComponent

from component_library.status import COMPONENT_IMPLEMENTATION_STATUS

_REGISTRY: dict[str, type[BaseComponent]] = {}


class ComponentDescription(BaseModel):
    component_id: str
    category: str
    version: str
    description: str
    config_schema_json: str
    status: str


def register(component_id: str):
    """Decorator to register a component class."""
    def decorator(cls: type[BaseComponent]) -> type[BaseComponent]:
        _REGISTRY[component_id] = cls
        return cls
    return decorator


def get_component(component_id: str) -> type[BaseComponent]:
    """Look up a component class by ID.

    Args:
        component_id: Library component identifier.

    Returns:
        The component class (not instantiated).

    Raises:
        KeyError: If the component_id is not registered.
    """
    if component_id not in _REGISTRY:
        raise KeyError(f"Component '{component_id}' not found in registry.")
    return _REGISTRY[component_id]


def list_components(category: str | None = None) -> list[str]:
    """List all registered component IDs, optionally filtered by category."""
    if category is None:
        return list(_REGISTRY.keys())
    return [cid for cid, cls in _REGISTRY.items() if getattr(cls, "category", "") == category]


def describe_all_components(*, production_only: bool = True) -> list[ComponentDescription]:
    _ensure_builtin_components_registered()
    descriptions: list[ComponentDescription] = []
    for component_id, cls in sorted(_REGISTRY.items()):
        status = COMPONENT_IMPLEMENTATION_STATUS.get(component_id, "stub")
        if production_only and status != "production":
            continue
        descriptions.append(
            ComponentDescription(
                component_id=component_id,
                category=str(getattr(cls, "category", "")),
                version=str(getattr(cls, "version", "latest")),
                description=(inspect.getdoc(cls) or "").split("\n\n")[0],
                config_schema_json=json.dumps(
                    getattr(cls, "config_schema", {}),
                    sort_keys=True,
                    default=str,
                ),
                status=status,
            )
        )
    return descriptions


def _ensure_builtin_components_registered() -> None:
    for package_name in (
        "component_library.models",
        "component_library.work",
        "component_library.tools",
        "component_library.data",
        "component_library.quality",
    ):
        package = importlib.import_module(package_name)
        for module_info in pkgutil.iter_modules(package.__path__, prefix=f"{package_name}."):
            if module_info.name.endswith(".__init__"):
                continue
            importlib.import_module(module_info.name)
