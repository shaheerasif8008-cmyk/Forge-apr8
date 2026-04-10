"""Pipeline worker: runs the full factory pipeline stages for a commission."""

from __future__ import annotations

import asyncio

import structlog

from factory.models.build import Build, BuildStatus
from factory.models.requirements import EmployeeRequirements
from factory.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def start_pipeline(requirements: EmployeeRequirements, build: Build) -> Build:
    """Run Architect → Builder → Evaluator → Deployer for a commission.

    Args:
        requirements: Validated requirements from the Analyst stage.
        build: Initialised Build record.

    Returns:
        Completed Build with final status.
    """
    from factory.pipeline.architect.designer import design_employee
    from factory.pipeline.builder.assembler import assemble
    from factory.pipeline.builder.generator import generate
    from factory.pipeline.builder.packager import package
    from factory.pipeline.evaluator.test_runner import evaluate
    from factory.pipeline.evaluator.self_correction import correction_loop
    from factory.models.deployment import Deployment

    logger.info("pipeline_start", build_id=str(build.id))
    try:
        blueprint = await design_employee(requirements)
        build.blueprint_id = blueprint.id

        build = await assemble(blueprint, build)
        build = await generate(blueprint, build)
        build = await package(build)
        build = await evaluate(build)

        if build.status == BuildStatus.FAILED:
            build = await correction_loop(blueprint, build)

        logger.info("pipeline_complete", status=build.status)
    except Exception as exc:
        logger.exception("pipeline_error", exc=str(exc))
        build.status = BuildStatus.FAILED

    return build


@celery_app.task(name="factory.workers.pipeline_worker.run_pipeline")
def run_pipeline(requirements_dict: dict, build_dict: dict) -> dict:
    """Celery task wrapper for the async pipeline."""
    requirements = EmployeeRequirements(**requirements_dict)
    build = Build(**build_dict)
    result = asyncio.get_event_loop().run_until_complete(start_pipeline(requirements, build))
    return result.model_dump()
