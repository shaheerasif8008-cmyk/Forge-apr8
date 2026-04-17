"""Assembler: creates the build directory for a deployable employee package."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import structlog

from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildLog, BuildStatus
from factory.models.requirements import EmployeeRequirements
from factory.pipeline.builder.config_generator import generate_config
from factory.pipeline.builder.deps_generator import generate_requirements_txt
from factory.pipeline.builder.dockerfile_generator import generate_dockerfile
from factory.pipeline.builder.entrypoint_generator import generate_entrypoint
from factory.pipeline.builder.env_generator import generate_env_example

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_ROOT = Path("/tmp/forge-builds")
FRAMEWORK_FILES = ("__init__.py", "interfaces.py", "registry.py", "component_factory.py")
DEFAULT_SIDEBAR_PANELS = (
    "inbox",
    "activity",
    "documents",
    "memory",
    "settings",
    "updates",
    "metrics",
)


async def assemble(
    blueprint: EmployeeBlueprint,
    requirements: EmployeeRequirements,
    build: Build,
) -> Build:
    """Create a self-contained build directory from a blueprint."""
    build.status = BuildStatus.ASSEMBLING
    build.metadata.setdefault("requirements_id", str(requirements.id))

    build_dir = BUILD_ROOT / str(build.id)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    logger.info("assembler_start", build_id=str(build.id), build_dir=str(build_dir))

    shutil.copytree(REPO_ROOT / "employee_runtime", build_dir / "employee_runtime")
    (build_dir / "portal").mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "portal" / "employee_app", build_dir / "portal" / "employee_app")
    _write_employee_app_config(blueprint, requirements, build_dir)
    _copy_component_framework(build_dir / "component_library")

    copied_components: list[str] = []
    for component in blueprint.components:
        _copy_component(component.category, component.component_id, build_dir / "component_library")
        copied_components.append(f"{component.category}/{component.component_id}")
        build.logs.append(
            BuildLog(
                stage="assembler",
                message=f"Copied component: {component.category}/{component.component_id}",
                detail={"config": component.config},
            )
        )

    generated_dir = build_dir / "generated"
    generated_dir.mkdir(exist_ok=True)
    (generated_dir / "__init__.py").write_text("")

    config = await generate_config(blueprint, requirements, build_dir=str(build_dir), generated_files=[])
    config_path = build_dir / "config.yaml"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True))
    manifest_path = build_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(config.get("manifest", {}), indent=2, sort_keys=True))

    await generate_entrypoint(build_dir)
    await generate_dockerfile(build_dir)
    await generate_requirements_txt(build_dir)
    await generate_env_example(build_dir)

    build.metadata.update(
        {
            "build_dir": str(build_dir),
            "config_path": str(config_path),
            "manifest_path": str(manifest_path),
            "copied_components": copied_components,
            "generated_dir": str(generated_dir),
            "workflow_id": blueprint.workflow_id,
            "deployment_format": blueprint.deployment_spec.format,
            "employee_id": str(blueprint.id),
            "employee_name": blueprint.employee_name,
            "employee_role": requirements.role_title or requirements.name,
            "frontend_dir": str(build_dir / "portal" / "employee_app"),
            "enabled_sidebar_panels": _enabled_sidebar_panels(blueprint),
            "desktop_backend_url": blueprint.deployment_spec.hosted_base_url,
        }
    )
    build.logs.append(
        BuildLog(
            stage="assembler",
            message="Build directory assembled",
            detail={"build_dir": str(build_dir), "component_count": len(copied_components)},
        )
    )
    logger.info("assembler_complete", build_id=str(build.id), component_count=len(copied_components))
    return build


def _copy_component_framework(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in FRAMEWORK_FILES:
        shutil.copy2(REPO_ROOT / "component_library" / filename, destination / filename)


def _copy_component(category: str, component_id: str, destination: Path) -> None:
    category_src = REPO_ROOT / "component_library" / category
    category_dest = destination / category
    category_dest.mkdir(parents=True, exist_ok=True)

    init_src = category_src / "__init__.py"
    if init_src.exists():
        shutil.copy2(init_src, category_dest / "__init__.py")
    else:
        (category_dest / "__init__.py").write_text("")

    src = category_src / f"{component_id}.py"
    if not src.exists():
        raise FileNotFoundError(f"Component source not found: {src}")
    shutil.copy2(src, category_dest / f"{component_id}.py")

    if category == "work":
        schemas_src = category_src / "schemas.py"
        if schemas_src.exists():
            shutil.copy2(schemas_src, category_dest / "schemas.py")


def _write_employee_app_config(
    blueprint: EmployeeBlueprint,
    requirements: EmployeeRequirements,
    build_dir: Path,
) -> None:
    employee_app_dir = build_dir / "portal" / "employee_app"
    config_path = employee_app_dir / "app" / "config.ts"
    enabled_panels = _enabled_sidebar_panels(blueprint)
    config_contents = (
        "export type EmployeeAppConfig = {\n"
        "  employeeId: string;\n"
        "  employeeName: string;\n"
        "  employeeRole: string;\n"
        "  enabledSidebarPanels: string[];\n"
        "  apiBaseUrl: string;\n"
        "  wsBaseUrl: string;\n"
        "  deploymentFormat: string;\n"
        "};\n\n"
        "export const employeeAppConfig: EmployeeAppConfig = {\n"
        f"  employeeId: {json.dumps(str(blueprint.id))},\n"
        f"  employeeName: {json.dumps(blueprint.employee_name)},\n"
        f"  employeeRole: {json.dumps(requirements.role_title or requirements.name)},\n"
        f"  enabledSidebarPanels: {json.dumps(enabled_panels)},\n"
        "  apiBaseUrl: \"\",\n"
        "  wsBaseUrl: \"\",\n"
        f"  deploymentFormat: {json.dumps(blueprint.deployment_spec.format)},\n"
        "};\n"
    )
    config_path.write_text(config_contents)


def _enabled_sidebar_panels(blueprint: EmployeeBlueprint) -> list[str]:
    component_ids = {component.component_id for component in blueprint.components}
    panels = list(DEFAULT_SIDEBAR_PANELS)
    if "working_memory" not in component_ids and "operational_memory" not in component_ids:
        panels.remove("memory")
    if "audit_system" not in component_ids:
        panels.remove("activity")
    if not any(component_id.endswith("_tool") for component_id in component_ids):
        panels.remove("documents")
    if "approval_manager" not in component_ids and "autonomy_manager" not in component_ids:
        panels.remove("inbox")
    return panels
