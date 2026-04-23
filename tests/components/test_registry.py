"""Tests for the component registry."""

from __future__ import annotations

import json

# Import side effects — trigger all @register decorators
import component_library.models.anthropic_provider  # noqa: F401
import component_library.models.litellm_router  # noqa: F401
from component_library.registry import describe_all_components, get_component, list_components


def test_anthropic_provider_registered() -> None:
    cls = get_component("anthropic_provider")
    assert cls.component_id == "anthropic_provider"


def test_list_components_by_category() -> None:
    model_components = list_components(category="models")
    assert "anthropic_provider" in model_components


def test_unknown_component_raises() -> None:
    import pytest
    with pytest.raises(KeyError):
        get_component("nonexistent_component_xyz")


def test_describe_all_components_includes_real_config_schemas() -> None:
    descriptions = describe_all_components()
    assert descriptions

    empty = [description.component_id for description in descriptions if description.config_schema_json == "{}"]
    assert empty == []

    schemas = {
        description.component_id: json.loads(description.config_schema_json)
        for description in descriptions
    }
    assert "primary_model" in schemas["litellm_router"]
    assert schemas["litellm_router"]["primary_model"]["required"] is True
    assert "tenant_id" in schemas["knowledge_base"]
    assert "provider" in schemas["search_tool"]
