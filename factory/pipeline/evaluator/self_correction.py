"""Self-correction loop: feeds Evaluator failures back to the Generator."""

from __future__ import annotations

import structlog

from factory.config import get_settings
from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildStatus
from factory.pipeline.builder.generator import generate
from factory.pipeline.builder.packager import package
from factory.pipeline.evaluator.test_runner import evaluate

logger = structlog.get_logger(__name__)


async def correction_loop(blueprint: EmployeeBlueprint, build: Build) -> Build:
    """Retry generation and evaluation until the build passes or max iterations reached.

    Args:
        blueprint: Employee blueprint (used to re-generate).
        build: Current failing build.

    Returns:
        Build with final status (PASSED or FAILED after max iterations).
    """
    settings = get_settings()
    max_iter = settings.max_generation_iterations

    while build.status == BuildStatus.FAILED and build.iteration < max_iter:
        build.iteration += 1
        logger.warning(
            "self_correction_retry",
            iteration=build.iteration,
            max=max_iter,
            build_id=str(build.id),
        )
        build = await generate(blueprint, build, iteration=build.iteration)
        build = await package(build)
        build = await evaluate(build)

    if build.status == BuildStatus.FAILED:
        logger.error("self_correction_exhausted", build_id=str(build.id))

    return build
