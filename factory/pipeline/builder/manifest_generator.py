"""Build canonical package manifests from blueprints and requirements."""

from __future__ import annotations

from factory.models.blueprint import EmployeeBlueprint
from factory.models.package_manifest import ArtifactManifest, IdentityLayers, PackageManifest
from factory.models.requirements import EmployeeRequirements


def select_runtime_template(deployment_format: str) -> str:
    normalized = deployment_format.strip().lower()
    if normalized == "server":
        return "server_compose_bundle"
    if normalized in {"desktop", "hybrid"}:
        return "desktop_electron_shell"
    return "container_service"


def build_package_manifest(
    blueprint: EmployeeBlueprint,
    requirements: EmployeeRequirements,
    *,
    build_dir: str = "",
    generated_files: list[str] | None = None,
) -> PackageManifest:
    return PackageManifest(
        employee_id=blueprint.id,
        org_id=blueprint.org_id,
        employee_name=blueprint.employee_name,
        role_title=requirements.role_title or requirements.name,
        employee_type=blueprint.employee_type,
        workflow=blueprint.workflow_id,
        identity_layers=IdentityLayers(
            layer_1_core_identity=blueprint.identity_layers.core_identity,
            layer_2_role_definition=blueprint.identity_layers.role_definition,
            layer_3_organizational_map=blueprint.identity_layers.organizational_map,
            layer_4_behavioral_rules=blueprint.identity_layers.behavioral_rules,
            layer_5_retrieved_context=blueprint.identity_layers.retrieved_context,
            layer_6_self_awareness=blueprint.identity_layers.self_awareness,
        ),
        components=blueprint.components,
        tool_permissions=blueprint.tool_permissions,
        autonomy_policy=blueprint.autonomy_profile,
        monitoring=blueprint.monitoring_policy,
        updates=requirements.update_preferences.model_dump(mode="json"),
        deployment=blueprint.deployment_spec,
        ui=blueprint.ui_profile,
        communication_channels=requirements.communication_channels,
        org_map=[contact.model_dump(mode="json") for contact in requirements.org_map],
        authority_matrix={key: value.value for key, value in requirements.authority_matrix.items()},
        artifact_manifest=ArtifactManifest(
            build_dir=build_dir,
            generated_files=generated_files or [],
            runtime_template=select_runtime_template(blueprint.deployment_spec.format),
        ),
    )
