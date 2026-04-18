from __future__ import annotations

import pytest

from factory.models.blueprint import SelectedComponent
from factory.models.requirements import EmployeeArchetype
from factory.pipeline.architect.component_selector import ArchitectError, select_components


@pytest.mark.anyio
async def test_architect_llm_selector_legal_intake(sample_requirements, monkeypatch) -> None:
    monkeypatch.setattr("factory.pipeline.architect.component_selector.get_settings", lambda: type("Settings", (), {"use_llm_architect": True, "generator_model": "test", "anthropic_api_key": ""})())

    async def fake_call_selector_llm(prompt: str) -> list[SelectedComponent]:
        return [
            SelectedComponent(category="models", component_id="litellm_router", rationale="llm routing"),
            SelectedComponent(category="work", component_id="text_processor", rationale="parse intake"),
            SelectedComponent(category="work", component_id="document_analyzer", rationale="analyze intake"),
            SelectedComponent(category="work", component_id="draft_generator", rationale="generate brief"),
            SelectedComponent(category="tools", component_id="email_tool", rationale="email"),
            SelectedComponent(category="tools", component_id="crm_tool", rationale="crm"),
            SelectedComponent(category="data", component_id="operational_memory", rationale="memory"),
            SelectedComponent(category="data", component_id="working_memory", rationale="working memory"),
            SelectedComponent(category="data", component_id="context_assembler", rationale="context"),
            SelectedComponent(category="data", component_id="org_context", rationale="org"),
            SelectedComponent(category="quality", component_id="confidence_scorer", rationale="score"),
            SelectedComponent(category="quality", component_id="audit_system", rationale="audit"),
            SelectedComponent(category="quality", component_id="input_protection", rationale="sanitize"),
            SelectedComponent(category="quality", component_id="verification_layer", rationale="verify"),
        ]

    monkeypatch.setattr("factory.pipeline.architect.component_selector._call_selector_llm", fake_call_selector_llm)
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    assert {"text_processor", "document_analyzer", "email_tool", "operational_memory", "audit_system"} <= component_ids


@pytest.mark.anyio
async def test_architect_llm_selector_executive_assistant(sample_requirements, monkeypatch) -> None:
    sample_requirements.employee_type = EmployeeArchetype.EXECUTIVE_ASSISTANT
    sample_requirements.required_tools = ["email", "calendar", "slack", "crm"]
    monkeypatch.setattr("factory.pipeline.architect.component_selector.get_settings", lambda: type("Settings", (), {"use_llm_architect": True, "generator_model": "test", "anthropic_api_key": ""})())

    async def fake_call_selector_llm(prompt: str) -> list[SelectedComponent]:
        return [
            SelectedComponent(category="models", component_id="anthropic_provider", rationale="assistant model"),
            SelectedComponent(category="work", component_id="workflow_executor", rationale="plan work"),
            SelectedComponent(category="work", component_id="communication_manager", rationale="communications"),
            SelectedComponent(category="work", component_id="scheduler_manager", rationale="calendar"),
            SelectedComponent(category="tools", component_id="email_tool", rationale="email"),
            SelectedComponent(category="tools", component_id="calendar_tool", rationale="calendar"),
            SelectedComponent(category="tools", component_id="messaging_tool", rationale="slack"),
            SelectedComponent(category="tools", component_id="crm_tool", rationale="crm"),
        ]

    monkeypatch.setattr("factory.pipeline.architect.component_selector._call_selector_llm", fake_call_selector_llm)
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    assert {"scheduler_manager", "calendar_tool", "messaging_tool", "crm_tool"} <= component_ids


@pytest.mark.anyio
async def test_architect_llm_selector_compound_requirement(sample_requirements, monkeypatch) -> None:
    sample_requirements.required_tools = ["email", "calendar", "crm"]
    monkeypatch.setattr("factory.pipeline.architect.component_selector.get_settings", lambda: type("Settings", (), {"use_llm_architect": True, "generator_model": "test", "anthropic_api_key": ""})())

    async def fake_call_selector_llm(prompt: str) -> list[SelectedComponent]:
        return [
            SelectedComponent(category="models", component_id="litellm_router", rationale="llm"),
            SelectedComponent(category="work", component_id="text_processor", rationale="parse"),
            SelectedComponent(category="work", component_id="document_analyzer", rationale="analyze"),
            SelectedComponent(category="work", component_id="draft_generator", rationale="draft"),
            SelectedComponent(category="tools", component_id="email_tool", rationale="email"),
            SelectedComponent(category="tools", component_id="calendar_tool", rationale="calendar"),
            SelectedComponent(category="tools", component_id="crm_tool", rationale="crm"),
            SelectedComponent(category="data", component_id="operational_memory", rationale="memory"),
            SelectedComponent(category="data", component_id="working_memory", rationale="memory"),
            SelectedComponent(category="data", component_id="context_assembler", rationale="context"),
            SelectedComponent(category="data", component_id="org_context", rationale="org"),
            SelectedComponent(category="quality", component_id="confidence_scorer", rationale="score"),
            SelectedComponent(category="quality", component_id="audit_system", rationale="audit"),
            SelectedComponent(category="quality", component_id="input_protection", rationale="sanitize"),
            SelectedComponent(category="quality", component_id="verification_layer", rationale="verify"),
        ]

    monkeypatch.setattr("factory.pipeline.architect.component_selector._call_selector_llm", fake_call_selector_llm)
    components = await select_components(sample_requirements)
    component_ids = {component.component_id for component in components}
    assert {"email_tool", "calendar_tool", "crm_tool"} <= component_ids


@pytest.mark.anyio
async def test_architect_llm_selector_rejects_unsatisfied_requirement(sample_requirements, monkeypatch) -> None:
    sample_requirements.required_tools = ["calendar"]
    monkeypatch.setattr("factory.pipeline.architect.component_selector.get_settings", lambda: type("Settings", (), {"use_llm_architect": True, "generator_model": "test", "anthropic_api_key": ""})())

    async def fake_call_selector_llm(prompt: str) -> list[SelectedComponent]:
        return [
            SelectedComponent(category="models", component_id="litellm_router", rationale="llm"),
            SelectedComponent(category="work", component_id="text_processor", rationale="parse"),
            SelectedComponent(category="work", component_id="document_analyzer", rationale="analyze"),
            SelectedComponent(category="work", component_id="draft_generator", rationale="draft"),
        ]

    monkeypatch.setattr("factory.pipeline.architect.component_selector._call_selector_llm", fake_call_selector_llm)
    with pytest.raises(ArchitectError):
        await select_components(sample_requirements)
