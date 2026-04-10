"""Blueprint builder: assembles the final EmployeeBlueprint."""

from __future__ import annotations

from factory.models.blueprint import CustomCodeSpec, EmployeeBlueprint, SelectedComponent
from factory.models.requirements import EmployeeRequirements, RiskTier


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

    return EmployeeBlueprint(
        requirements_id=requirements.id,
        org_id=requirements.org_id,
        employee_name=requirements.name,
        components=components,
        custom_code_specs=gaps,
        workflow_description=f"Employee: {requirements.name}. {requirements.role_summary}",
        autonomy_profile=autonomy_profile,
        architect_reasoning=(
            f"Selected {len(components)} components, {len(gaps)} custom specs. "
            f"Risk tier: {requirements.risk_tier.value}."
        ),
    )
