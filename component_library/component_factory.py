"""Helpers for building initialized component maps."""

from __future__ import annotations

from component_library.interfaces import BaseComponent
from component_library.registry import get_component


async def create_components(
    component_ids: list[str],
    config: dict[str, dict],
) -> dict[str, BaseComponent]:
    """Instantiate and initialize a set of components from config."""

    components: dict[str, BaseComponent] = {}
    for component_id in component_ids:
        cls = get_component(component_id)
        instance = cls()
        await instance.initialize(config.get(component_id, {}))
        components[component_id] = instance
    return components
