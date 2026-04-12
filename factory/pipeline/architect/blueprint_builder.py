"""Blueprint builder: assembles the final EmployeeBlueprint."""

from __future__ import annotations

from factory.models.blueprint import (
    CustomCodeSpec,
    DeploymentSpec,
    EmployeeBlueprint,
    IdentityLayerInputs,
    MonitoringPolicy,
    SelectedComponent,
    UIProfile,
)
from factory.models.requirements import EmployeeArchetype, EmployeeRequirements, RiskTier


async def assemble_blueprint(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
    gaps: list[CustomCodeSpec],
) -> EmployeeBlueprint:
    """Assemble all architect outputs into a final EmployeeBlueprint.

    Args:
        requirements: Source requirements document.
        components: Selected library components.
        gaps: Custom code specifications for the Generator.

    Returns:
        Complete EmployeeBlueprint.
    """
    autonomy_profile: dict[str, object] = {
        "auto_approve_threshold": 0.85,
        "escalate_threshold": 0.60,
        "block_threshold": 0.40,
        "irreversible_actions_require_human": True,
        "risk_tier": requirements.risk_tier.value,
    }
    if requirements.risk_tier == RiskTier.CRITICAL:
        autonomy_profile["auto_approve_threshold"] = 0.95
        autonomy_profile["always_require_human_approval"] = True

    workflow_id = (
        "executive_assistant"
        if requirements.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT
        else "legal_intake"
    )
    component_ids = [component.component_id for component in components]
    tool_permissions = [component_id for component_id in component_ids if component_id.endswith("_tool")]
    identity_layers = IdentityLayerInputs(
        core_identity=(
            "You are a Forge AI Employee. You do real work end-to-end, behave like a human colleague, "
            "surface uncertainty honestly, and maintain an audit trail."
        ),
        role_definition=(
            f"You are {requirements.name}, serving as a "
            f"{requirements.role_title or requirements.employee_type.value.replace('_', ' ')}."
        ),
        organizational_map=(
            f"Supervisor email: {requirements.supervisor_email or 'unassigned'}. "
            f"Known org contacts: {', '.join(contact.name for contact in requirements.org_map) or 'none'}."
        ),
        behavioral_rules=(
            "Direct commands override portal rules, which override adaptive learning. "
            + " ".join(rule.description for rule in requirements.communication_rules[:4])
        ),
        self_awareness=(
            f"Workflow: {workflow_id}. Components available: {', '.join(component_ids)}. "
            f"Tool permissions: {', '.join(tool_permissions) or 'none'}."
        ),
    )
    monitoring_policy = MonitoringPolicy(
        health_check_interval_minutes=requirements.monitoring_preferences.health_check_interval_minutes,
        drift_detection_enabled=requirements.monitoring_preferences.drift_detection_enabled,
        alert_channels=requirements.monitoring_preferences.alert_channels,
    )
    deployment_spec = DeploymentSpec(
        format=requirements.deployment_format,
        target=requirements.deployment_target,
    )
    ui_profile = UIProfile(
        app_title=requirements.name,
        app_badge=requirements.deployment_target.replace("_", " ").title(),
        capabilities=requirements.primary_responsibilities[:6],
    )

    return EmployeeBlueprint(
        requirements_id=requirements.id,
        org_id=requirements.org_id,
        employee_type=requirements.employee_type,
        employee_name=requirements.name,
        components=components,
        custom_code_specs=gaps,
        workflow_id=workflow_id,
        tool_permissions=tool_permissions,
        identity_layers=identity_layers,
        workflow_description=f"Employee: {requirements.name}. {requirements.role_summary}",
        autonomy_profile=autonomy_profile,
        monitoring_policy=monitoring_policy,
        deployment_spec=deployment_spec,
        ui_profile=ui_profile,
        architect_reasoning=(
            f"Selected {len(components)} components, {len(gaps)} custom specs. "
            f"Risk tier: {requirements.risk_tier.value}."
        ),
    )
