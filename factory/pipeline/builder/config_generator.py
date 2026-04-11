"""Generate runtime config for packaged employees."""

from __future__ import annotations

from typing import Any

from factory.models.blueprint import EmployeeBlueprint
from factory.models.requirements import EmployeeRequirements


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


async def generate_config(
    blueprint: EmployeeBlueprint,
    requirements: EmployeeRequirements,
) -> dict[str, Any]:
    """Generate the runtime config used by the packaged employee."""
    org_context = requirements.org_context if isinstance(requirements.org_context, dict) else {}
    firm_info = _as_dict(org_context.get("firm_info"))
    practice_areas = _as_list(
        org_context.get("practice_areas", firm_info.get("practice_areas", []))
    )

    return {
        "employee_id": str(blueprint.id),
        "org_id": str(blueprint.org_id),
        "employee_name": blueprint.employee_name,
        "workflow": "legal_intake",
        "components": [
            {"id": component.component_id, "category": component.category, "config": component.config}
            for component in blueprint.components
        ],
        "autonomy": blueprint.autonomy_profile,
        "communication_channels": requirements.communication_channels,
        "supervisor_email": requirements.supervisor_email,
        "deployment_format": requirements.deployment_format,
        "system_identity": blueprint.workflow_description,
        "people": _as_list(org_context.get("people")),
        "escalation_chain": _as_list(org_context.get("escalation_chain")),
        "firm_info": firm_info,
        "practice_areas": practice_areas,
        "default_attorney": org_context.get("default_attorney", "Forge Review"),
    }
