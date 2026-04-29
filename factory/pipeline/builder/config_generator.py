"""Generate runtime config for packaged employees."""

from __future__ import annotations

import secrets
from typing import Any

from factory.models.blueprint import EmployeeBlueprint
from factory.models.requirements import EmployeeRequirements
from factory.pipeline.builder.manifest_generator import build_package_manifest
from factory.config import get_settings
from employee_runtime.workflow_packs import select_pack_ids


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
    workflow_packs = select_pack_ids(
        requirements.role_title or requirements.name,
        list(requirements.required_tools),
    )
    kernel_baseline = {
        "version": "1.0.0",
        "required_lanes": ["knowledge_work", "business_process", "hybrid"],
        "certification_required": True,
    }
    manifest_payload = manifest.model_dump(mode="json")
    manifest_payload.update(
        {
            "workflow_packs": workflow_packs,
            "kernel_baseline": kernel_baseline,
        }
    )

    config: dict[str, Any] = dict(manifest_payload)
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
        "workflow_packs": workflow_packs,
        "kernel_baseline": kernel_baseline,
        "system_identity": blueprint.workflow_description,
        "people": _as_list(org_context.get("people")),
        "escalation_chain": _as_list(org_context.get("escalation_chain")),
        "firm_info": firm_info,
        "practice_areas": practice_areas,
        "default_attorney": org_context.get("default_attorney", "Forge Review"),
        "deliberation_council": _deliberation_config(blueprint),
        "manifest": manifest_payload,
    })
    return config


def _deliberation_config(blueprint: EmployeeBlueprint) -> dict[str, object]:
    component_ids = {component.component_id for component in blueprint.components}
    if "adversarial_review" not in component_ids:
        return {}
    settings = get_settings()
    if settings.openrouter_api_key:
        primary = settings.llm_primary_model
        fallback = settings.llm_fallback_model
    elif settings.openai_api_key:
        primary = "gpt-4o"
        fallback = "gpt-4o-mini"
    else:
        primary = settings.llm_primary_model
        fallback = settings.llm_fallback_model
    return {
        "advocate_models": [primary, fallback],
        "challenger_models": [fallback, primary],
        "adjudicator_model": primary,
        "max_reruns": 3,
        "max_time_seconds": 600,
        "trigger_conditions": ["high_risk_output", "irreversible_action"],
    }
