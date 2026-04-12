"""Component registry — discovers and instantiates library components by ID."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from component_library.interfaces import BaseComponent

_REGISTRY: dict[str, type[BaseComponent]] = {}


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
