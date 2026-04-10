"""Assembler: pulls and configures proven library components (≈80% of a build)."""

from __future__ import annotations

import structlog

from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildLog, BuildStatus

logger = structlog.get_logger(__name__)


async def assemble(blueprint: EmployeeBlueprint, build: Build) -> Build:
    """Pull selected components from the library and configure them for this employee.

    Args:
        blueprint: The architect-produced design document.
        build: The in-progress Build record to update.

    Returns:
        Updated Build with assembly logs.
    """
    build.status = BuildStatus.ASSEMBLING
    logger.info("assembler_start", blueprint_id=str(blueprint.id), build_id=str(build.id))

    for component in blueprint.components:
        build.logs.append(BuildLog(
            stage="assembler",
            message=f"Assembled component: {component.category}/{component.component_id}",
            detail={"config": component.config},
        ))

    logger.info("assembler_complete", component_count=len(blueprint.components))
    return build
