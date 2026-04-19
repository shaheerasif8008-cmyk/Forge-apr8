from __future__ import annotations

from factory.models.blueprint import EmployeeBlueprint, SelectedComponent
from factory.models.requirements import EmployeeArchetype, EmployeeRequirements
from factory.pipeline.builder.manifest_generator import build_package_manifest


def test_manifest_generator_supports_executive_assistant(sample_org) -> None:
    requirements = EmployeeRequirements(
        org_id=sample_org.id,
        employee_type=EmployeeArchetype.EXECUTIVE_ASSISTANT,
        name="Avery",
        role_title="Executive Assistant",
        role_summary="Coordinates inbox, calendar, and follow-up work for the CEO.",
        primary_responsibilities=["coordinate scheduling", "draft follow-ups", "update CRM"],
        required_tools=["email", "calendar", "slack", "crm"],
        communication_channels=["email", "slack"],
    )
    blueprint = EmployeeBlueprint(
        requirements_id=requirements.id,
        org_id=requirements.org_id,
        employee_type=requirements.employee_type,
        employee_name=requirements.name,
        workflow_id="executive_assistant",
        tool_permissions=["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
        components=[
            SelectedComponent(category="work", component_id="workflow_executor"),
            SelectedComponent(category="work", component_id="communication_manager"),
            SelectedComponent(category="tools", component_id="calendar_tool"),
        ],
    )

    manifest = build_package_manifest(blueprint, requirements)

    assert manifest.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT
    assert manifest.workflow == "executive_assistant"
    assert manifest.role_title == "Executive Assistant"
    assert "calendar_tool" in manifest.tool_permissions
    assert manifest.artifact_manifest.runtime_template == "container_service"
