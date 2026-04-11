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

    config = await generate_config(blueprint, requirements)
    config_path = build_dir / "config.yaml"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True))

    await generate_entrypoint(build_dir)
    await generate_dockerfile(build_dir)
    await generate_requirements_txt(build_dir)
    await generate_env_example(build_dir)

    build.metadata.update(
        {
            "build_dir": str(build_dir),
            "config_path": str(config_path),
            "copied_components": copied_components,
            "generated_dir": str(generated_dir),
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
