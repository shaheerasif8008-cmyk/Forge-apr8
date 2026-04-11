"""Pipeline worker: runs the full factory pipeline stages for a commission."""

from __future__ import annotations

import asyncio
from datetime import datetime

import structlog

from factory.database import get_session_factory, init_engine
from factory.models.build import Build, BuildStatus
from factory.models.deployment import Deployment, DeploymentStatus
from factory.models.requirements import EmployeeRequirements
from factory.persistence import save_blueprint, save_build, save_deployment, save_requirements
from factory.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _ensure_session_factory():
    try:
        return get_session_factory()
    except RuntimeError:
        init_engine()
        return get_session_factory()


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
    from factory.pipeline.deployer.activator import activate
    from factory.pipeline.deployer.provisioner import provision

    session_factory = _ensure_session_factory()
    build.requirements_id = requirements.id
    logger.info("pipeline_start", build_id=str(build.id))
    try:
        async with session_factory() as session:
            await save_requirements(session, requirements)
            await save_build(session, build)
            await session.commit()

            blueprint = await design_employee(requirements)
            build.blueprint_id = blueprint.id

            await save_blueprint(session, blueprint)
            await save_build(session, build)
            await session.commit()

            build = await assemble(blueprint, requirements, build)
            await save_build(session, build)
            await session.commit()

            build = await generate(blueprint, build)
            await save_build(session, build)
            await session.commit()

            build = await package(build)
            await save_build(session, build)
            await session.commit()

            build = await evaluate(build)
            await save_build(session, build)
            await session.commit()

            if build.status == BuildStatus.FAILED:
                build = await correction_loop(blueprint, build)
                await save_build(session, build)
                await session.commit()

            if build.status == BuildStatus.PASSED:
                build.status = BuildStatus.DEPLOYING
                await save_build(session, build)
                await session.commit()

                deployment = Deployment(
                    build_id=build.id,
                    org_id=requirements.org_id,
                    format=requirements.deployment_format,
                    status=DeploymentStatus.PENDING,
                )
                deployment = await provision(deployment, build)
                deployment = await activate(deployment)
                await save_deployment(session, deployment)
                build.status = (
                    BuildStatus.DEPLOYED
                    if deployment.status == DeploymentStatus.ACTIVE
                    else BuildStatus.FAILED
                )
                build.completed_at = datetime.utcnow()
                await save_build(session, build)
                await session.commit()

            logger.info("pipeline_complete", status=build.status)
    except Exception as exc:
        logger.exception("pipeline_error", exc=str(exc))
        build.status = BuildStatus.FAILED
        try:
            async with session_factory() as session:
                await save_build(session, build)
                await session.commit()
        except Exception:
            logger.exception("pipeline_error_persist_failed", build_id=str(build.id))

    return build


@celery_app.task(name="factory.workers.pipeline_worker.run_pipeline")
def run_pipeline(requirements_dict: dict, build_dict: dict) -> dict:
    """Celery task wrapper for the async pipeline."""
    requirements = EmployeeRequirements(**requirements_dict)
    build = Build(**build_dict)
    result = asyncio.get_event_loop().run_until_complete(start_pipeline(requirements, build))
    return result.model_dump()
