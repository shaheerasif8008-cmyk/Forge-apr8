"""Tests for the component registry."""

from __future__ import annotations

# Import side effects — trigger all @register decorators
import component_library.models.anthropic_provider  # noqa: F401
import component_library.models.litellm_router  # noqa: F401

from component_library.registry import get_component, list_components


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
