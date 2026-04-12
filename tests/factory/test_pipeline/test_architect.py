"""Tests for the Architect pipeline stage."""

from __future__ import annotations

import pytest

from factory.models.requirements import EmployeeRequirements, RiskTier
from factory.pipeline.architect.blueprint_builder import assemble_blueprint
from factory.pipeline.architect.component_selector import select_components
from factory.pipeline.architect.gap_analyzer import identify_gaps


@pytest.mark.anyio
async def test_component_selector_always_includes_model(
    sample_requirements: EmployeeRequirements,
) -> None:
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    assert "anthropic_provider" in component_ids
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
async def test_blueprint_assembly(sample_requirements: EmployeeRequirements) -> None:
    components = await select_components(sample_requirements)
    gaps = await identify_gaps(sample_requirements, components)
    blueprint = await assemble_blueprint(sample_requirements, components, gaps)
    assert blueprint.employee_name == sample_requirements.name
    assert blueprint.org_id == sample_requirements.org_id
    assert len(blueprint.components) > 0
