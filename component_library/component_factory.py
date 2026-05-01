"""Helpers for building initialized component maps."""

from __future__ import annotations

from typing import Any

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
    _wire_model_clients(components)
    return components


def _wire_model_clients(components: dict[str, BaseComponent]) -> None:
    model_client: Any | None = components.get("litellm_router") or components.get("anthropic_provider")
    if model_client is None:
        return
    for component_id in ("text_processor", "document_analyzer", "draft_generator", "workflow_executor"):
        component = components.get(component_id)
        if component is None:
            continue
        setter = getattr(component, "set_model_client", None)
        if callable(setter):
            setter(model_client)
