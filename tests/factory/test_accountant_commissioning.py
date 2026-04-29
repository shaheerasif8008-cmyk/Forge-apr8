from __future__ import annotations

import pytest

from factory.commissioning.fixtures import load_requirements_fixture
from factory.models.requirements import EmployeeArchetype, RiskTier
from factory.pipeline.architect.designer import design_employee


@pytest.mark.anyio
async def test_accountant_fixture_is_valid_architect_input() -> None:
    requirements = load_requirements_fixture("accountant")

    assert requirements.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT
    assert requirements.name == "Finley"
    assert requirements.role_title == "AI Accountant"
    assert requirements.risk_tier == RiskTier.HIGH
    assert requirements.deployment_format == "server"
    assert "general_ledger" in requirements.required_data_sources
    assert "post_journal_entry" in requirements.authority_matrix

    blueprint = await design_employee(requirements)

    component_ids = {component.component_id for component in blueprint.components}
    assert blueprint.workflow_id == "executive_assistant"
    assert {"litellm_router", "workflow_executor", "communication_manager", "approval_manager"} <= component_ids
    assert blueprint.deployment_spec.format == "server"
    assert blueprint.ui_profile.app_title == "Finley"
    assert "AI Accountant" in blueprint.identity_layers.role_definition
