"""Generator: writes custom code for capabilities not covered by the library (≈20%)."""

from __future__ import annotations

from pathlib import Path

import structlog

from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildLog, BuildStatus

logger = structlog.get_logger(__name__)


async def generate(blueprint: EmployeeBlueprint, build: Build, iteration: int = 1) -> Build:
    """Generate custom code for each CustomCodeSpec in the blueprint.

    Args:
        blueprint: Architect-produced design with custom_code_specs.
        build: In-progress Build record.
        iteration: Current generation attempt (max MAX_GENERATION_ITERATIONS).

    Returns:
        Updated Build with generation logs.
    """
    build.status = BuildStatus.GENERATING
    logger.info(
        "generator_start",
        spec_count=len(blueprint.custom_code_specs),
        iteration=iteration,
    )

    generated_files: list[str] = []
    generated_dir = Path(str(build.metadata.get("generated_dir", "")))
    if blueprint.custom_code_specs and not generated_dir.exists():
        generated_dir.mkdir(parents=True, exist_ok=True)

    for spec in blueprint.custom_code_specs:
        file_path = generated_dir / f"{spec.name}.py"
        file_path.write_text(
            "\"\"\"Auto-generated custom capability stub.\"\"\"\n\n"
            f"SPEC_NAME = {spec.name!r}\n"
            f"SPEC_DESCRIPTION = {spec.description!r}\n"
        )
        generated_files.append(str(file_path))
        build.logs.append(BuildLog(
            stage="generator",
            message=f"Generated custom artifact: {spec.name}",
            detail={
                "description": spec.description,
                "iteration": iteration,
                "file_path": str(file_path),
            },
        ))

    build.metadata["generated_files"] = generated_files
    return build
