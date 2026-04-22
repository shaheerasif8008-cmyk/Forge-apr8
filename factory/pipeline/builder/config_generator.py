"""Generate runtime config for packaged employees."""

from __future__ import annotations

import secrets
from typing import Any

from factory.models.blueprint import EmployeeBlueprint
from factory.models.requirements import EmployeeRequirements
from factory.pipeline.builder.manifest_generator import build_package_manifest


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


async def generate_config(
    blueprint: EmployeeBlueprint,
    requirements: EmployeeRequirements,
    *,
    build_dir: str = "",
    generated_files: list[str] | None = None,
) -> dict[str, Any]:
    """Generate the runtime config used by the packaged employee."""
    org_context = requirements.org_context if isinstance(requirements.org_context, dict) else {}
    firm_info = _as_dict(org_context.get("firm_info"))
    practice_areas = _as_list(
        org_context.get("practice_areas", firm_info.get("practice_areas", []))
    )
    manifest = build_package_manifest(
        blueprint,
        requirements,
        build_dir=build_dir,
        generated_files=generated_files,
    )

    config: dict[str, Any] = manifest.model_dump(mode="json")
    api_auth_token = secrets.token_urlsafe(32)
    config.update({
        "employee_id": str(blueprint.id),
        "org_id": str(blueprint.org_id),
        "employee_name": blueprint.employee_name,
        "workflow": blueprint.workflow_id,
        "workflow_graph": blueprint.workflow_graph.model_dump(mode="json") if blueprint.workflow_graph else {},
        "employee_database_url": "",
        "employee_db_auto_init": True,
        "components": [
            {"id": component.component_id, "category": component.category, "config": component.config}
            for component in blueprint.components
        ],
        "autonomy": blueprint.autonomy_profile,
        "communication_channels": requirements.communication_channels,
        "supervisor_email": requirements.supervisor_email,
        "deployment_format": requirements.deployment_format,
        "auth_required": True,
        "api_auth_token": api_auth_token,
        "system_identity": blueprint.workflow_description,
        "people": _as_list(org_context.get("people")),
        "escalation_chain": _as_list(org_context.get("escalation_chain")),
        "firm_info": firm_info,
        "practice_areas": practice_areas,
        "default_attorney": org_context.get("default_attorney", "Forge Review"),
        "deliberation_council": _deliberation_config(blueprint),
        "manifest": manifest.model_dump(mode="json"),
    })
    return config


def _deliberation_config(blueprint: EmployeeBlueprint) -> dict[str, object]:
    component_ids = {component.component_id for component in blueprint.components}
    if "adversarial_review" not in component_ids:
        return {}
    return {
        "advocate_models": ["openrouter/anthropic/claude-3.5-sonnet", "openrouter/openai/gpt-4o"],
        "challenger_models": ["openrouter/openai/gpt-4o", "openrouter/anthropic/claude-3.5-haiku"],
        "adjudicator_model": "openrouter/anthropic/claude-3.5-sonnet",
        "max_reruns": 3,
        "max_time_seconds": 600,
        "trigger_conditions": ["high_risk_output", "irreversible_action"],
    }
