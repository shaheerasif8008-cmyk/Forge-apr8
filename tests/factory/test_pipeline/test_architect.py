"""Tests for the Architect pipeline stage."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from factory.models.requirements import EmployeeRequirements, RiskTier
from factory.pipeline.architect.blueprint_builder import assemble_blueprint
from factory.pipeline.architect.component_selector import select_components
from factory.pipeline.architect.gap_analyzer import identify_gaps
from factory.pipeline.architect.workflow_designer import design_workflow


@pytest.mark.anyio
async def test_component_selector_always_includes_model(
    sample_requirements: EmployeeRequirements,
) -> None:
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    assert "litellm_router" in component_ids
    assert {
        "text_processor",
        "document_analyzer",
        "draft_generator",
        "email_tool",
        "operational_memory",
        "working_memory",
        "context_assembler",
        "org_context",
        "confidence_scorer",
        "audit_system",
        "input_protection",
        "verification_layer",
    } <= component_ids


@pytest.mark.anyio
async def test_component_selector_prefers_openai_router_when_configured(
    sample_requirements: EmployeeRequirements,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "factory.pipeline.architect.component_selector.get_settings",
        lambda: SimpleNamespace(
            openai_api_key="sk-test",
            llm_primary_model="openrouter/anthropic/claude-3.5-sonnet",
            llm_fallback_model="openrouter/openai/gpt-4o",
            use_llm_architect=False,
        ),
    )

    components = await select_components(sample_requirements)
    router = next(component for component in components if component.component_id == "litellm_router")

    assert router.config["primary_model"] == "gpt-4o"
    assert router.config["fallback_model"] == "gpt-4o-mini"


@pytest.mark.anyio
async def test_high_risk_includes_adversarial_review(
    sample_requirements: EmployeeRequirements,
) -> None:
    sample_requirements.risk_tier = RiskTier.HIGH
    components = await select_components(sample_requirements)
    quality_ids = {c.component_id for c in components if c.category == "quality"}
    assert "adversarial_review" in quality_ids


@pytest.mark.anyio
async def test_gap_analyzer_flags_unknown_tools(
    sample_requirements: EmployeeRequirements,
) -> None:
    sample_requirements.required_tools = ["email", "proprietary_dms_system"]
    components = await select_components(sample_requirements)
    gaps = await identify_gaps(sample_requirements, components)
    gap_names = [g.name for g in gaps]
    assert any("proprietary_dms_system" in n for n in gap_names)
    assert not any("email" in n for n in gap_names)


@pytest.mark.anyio
async def test_messaging_tool_requirement_uses_existing_component(
    sample_requirements: EmployeeRequirements,
) -> None:
    sample_requirements.required_tools = ["email", "messaging"]
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    gaps = await identify_gaps(sample_requirements, components)
    gap_names = [gap.name for gap in gaps]

    assert "messaging_tool" in component_ids
    assert not any("messaging" in name for name in gap_names)


@pytest.mark.anyio
async def test_blueprint_assembly(sample_requirements: EmployeeRequirements) -> None:
    components = await select_components(sample_requirements)
    gaps = await identify_gaps(sample_requirements, components)
    workflow_graph = await design_workflow(sample_requirements, components, gaps)
    blueprint = await assemble_blueprint(sample_requirements, components, gaps, workflow_graph)
    assert blueprint.employee_name == sample_requirements.name
    assert blueprint.org_id == sample_requirements.org_id
    assert len(blueprint.components) > 0
    assert blueprint.workflow_graph is not None
