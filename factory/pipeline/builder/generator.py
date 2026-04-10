"""Generator: writes custom code for capabilities not covered by the library (≈20%)."""

from __future__ import annotations

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

    for spec in blueprint.custom_code_specs:
        # TODO: LLM-driven code generation via litellm + Instructor
        build.logs.append(BuildLog(
            stage="generator",
            message=f"Generated stub for: {spec.name}",
            detail={"description": spec.description, "iteration": iteration},
        ))

    return build
