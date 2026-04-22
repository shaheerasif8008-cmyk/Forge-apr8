"""Pipeline worker: runs the full factory pipeline stages for a commission."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import structlog

from factory.config import get_settings
from factory.database import get_session_factory, init_engine
from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildLog, BuildStatus
from factory.models.deployment import Deployment, DeploymentStatus
from factory.models.requirements import EmployeeRequirements
from factory.observability.langfuse_client import get_langfuse_client
from factory.persistence import (
    get_blueprint,
    get_build,
    get_requirements,
    save_blueprint,
    save_build,
    save_deployment,
    save_requirements,
)
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
    from factory.pipeline.evaluator.self_correction import correction_loop
    from factory.pipeline.evaluator.test_runner import evaluate

    session_factory = _ensure_session_factory()
    build.requirements_id = requirements.id
    logger.info("pipeline_start", build_id=str(build.id))
    try:
        with get_langfuse_client().trace(
            "factory_pipeline",
            input=requirements.model_dump(mode="json"),
            metadata={"build_id": str(build.id)},
            user_id=str(requirements.org_id),
            session_id=str(build.id),
        ) as trace:
            async with session_factory() as session:
                await save_requirements(session, requirements)
                await save_build(session, build)
                await session.commit()

                with get_langfuse_client().span("pipeline.architect", metadata={"build_id": str(build.id)}):
                    blueprint = await design_employee(requirements)
                build.blueprint_id = blueprint.id

                await save_blueprint(session, blueprint)
                await save_build(session, build)
                await session.commit()

                with get_langfuse_client().span("pipeline.assembler", metadata={"build_id": str(build.id)}):
                    build = await assemble(blueprint, requirements, build)
                await save_build(session, build)
                await session.commit()

                with get_langfuse_client().span("pipeline.generator", metadata={"build_id": str(build.id)}):
                    build = await generate(blueprint, build)
                await save_build(session, build)
                await session.commit()
                if build.status == BuildStatus.FAILED:
                    build.completed_at = datetime.now(UTC)
                    await save_build(session, build)
                    await session.commit()
                    logger.warning("pipeline_generation_failed", build_id=str(build.id))
                    trace.end(output=build.model_dump(mode="json"), metadata={"status": build.status.value})
                    return build

                with get_langfuse_client().span("pipeline.packager", metadata={"build_id": str(build.id)}):
                    build = await package(build)
                await save_build(session, build)
                await session.commit()

                with get_langfuse_client().span("pipeline.evaluator", metadata={"build_id": str(build.id)}):
                    build = await evaluate(build)
                await save_build(session, build)
                await session.commit()

                if build.status == BuildStatus.FAILED:
                    with get_langfuse_client().span("pipeline.self_correction", metadata={"build_id": str(build.id)}):
                        build = await correction_loop(blueprint, build)
                    await save_build(session, build)
                    await session.commit()

                if build.status == BuildStatus.PASSED:
                    if get_settings().human_review_required:
                        build.status = BuildStatus.PENDING_REVIEW
                        build.logs.append(
                            BuildLog(
                                timestamp=datetime.now(UTC),
                                stage="review",
                                level="info",
                                message="Build passed evaluation and is awaiting required human review before deployment.",
                                detail={},
                            )
                        )
                        await save_build(session, build)
                        await session.commit()
                    else:
                        build = await _deploy_build(session, requirements, blueprint, build)

                trace.end(output=build.model_dump(mode="json"), metadata={"status": build.status.value})
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


async def _deploy_build(
    session,
    requirements: EmployeeRequirements,
    blueprint: EmployeeBlueprint,
    build: Build,
) -> Build:
    from factory.pipeline.deployer.activator import activate
    from factory.pipeline.deployer.connector import Connector
    from factory.pipeline.deployer.provisioner import provision
    from factory.pipeline.deployer.rollback import rollback

    build.status = BuildStatus.DEPLOYING
    await save_build(session, build)
    await session.commit()

    deployment = Deployment(
        build_id=build.id,
        org_id=requirements.org_id,
        format=requirements.deployment_format,
        status=DeploymentStatus.PENDING,
    )
    connector = Connector()
    try:
        with get_langfuse_client().span("pipeline.provisioner", metadata={"build_id": str(build.id)}):
            deployment = await provision(deployment, build)
        with get_langfuse_client().span("pipeline.connector", metadata={"build_id": str(build.id)}):
            deployment = await connector.connect(deployment, blueprint)
        await save_deployment(session, deployment)
        await session.commit()
        if deployment.status != DeploymentStatus.PENDING_CLIENT_ACTION:
            with get_langfuse_client().span("pipeline.activator", metadata={"build_id": str(build.id)}):
                deployment = await activate(deployment)
    except Exception:
        logger.exception("pipeline_deploy_failure", build_id=str(build.id), deployment_id=str(deployment.id))
        with get_langfuse_client().span("pipeline.rollback", metadata={"build_id": str(build.id)}):
            deployment = await rollback(deployment, session)

    await save_deployment(session, deployment)
    if deployment.status == DeploymentStatus.ACTIVE:
        build.status = BuildStatus.DEPLOYED
    elif deployment.status == DeploymentStatus.PENDING_CLIENT_ACTION:
        build.status = BuildStatus.PENDING_CLIENT_ACTION
    else:
        build.status = BuildStatus.FAILED
    build.completed_at = datetime.now(UTC)
    await save_build(session, build)
    await session.commit()
    return build


async def resume_deployment(build_id: str) -> Build:
    build_uuid = UUID(build_id)
    session_factory = _ensure_session_factory()
    async with session_factory() as session:
        build = await get_build(session, build_uuid)
        if build is None:
            raise RuntimeError("build_not_found")
        if build.requirements_id is None or build.blueprint_id is None:
            raise RuntimeError("build_dependencies_missing")

        requirements = await get_requirements(session, build.requirements_id)
        blueprint = await get_blueprint(session, build.blueprint_id)
        if requirements is None or blueprint is None:
            raise RuntimeError("build_dependencies_missing")

        build.logs.append(
            BuildLog(
                timestamp=datetime.now(UTC),
                stage="review",
                level="info",
                message="Human review approved. Resuming deployment.",
                detail={},
            )
        )
        build.status = BuildStatus.PASSED
        build.completed_at = None
        build = await save_build(session, build)
        await session.commit()
        return await _deploy_build(session, requirements, blueprint, build)


@celery_app.task(name="factory.workers.pipeline_worker.resume_deployment")
def resume_deployment_task(build_id: str) -> dict:
    result = asyncio.get_event_loop().run_until_complete(resume_deployment(build_id))
    return result.model_dump()


@celery_app.task(name="factory.workers.pipeline_worker.run_pipeline")
def run_pipeline(requirements_dict: dict, build_dict: dict) -> dict:
    """Celery task wrapper for the async pipeline."""
    requirements = EmployeeRequirements(**requirements_dict)
    build = Build(**build_dict)
    result = asyncio.get_event_loop().run_until_complete(start_pipeline(requirements, build))
    return result.model_dump()
