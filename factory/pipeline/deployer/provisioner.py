"""Provisioner dispatcher for deployment providers."""

from __future__ import annotations

import structlog

from factory.models.build import Build
from factory.models.deployment import Deployment, DeploymentFormat
from factory.pipeline.deployer.providers.docker_compose_export import provision_server_export
from factory.pipeline.deployer.providers.local_docker import provision_local
from factory.pipeline.deployer.providers.railway import provision_railway

logger = structlog.get_logger(__name__)


async def provision(deployment: Deployment, build: Build) -> Deployment:
    logger.info("provision_dispatch", deployment_id=str(deployment.id), format=deployment.format.value)
    if deployment.format == DeploymentFormat.WEB:
        return await provision_railway(deployment, build)
    if deployment.format == DeploymentFormat.SERVER:
        return await provision_server_export(deployment, build)
    if deployment.format in (DeploymentFormat.LOCAL, DeploymentFormat.DESKTOP):
        return await provision_local(deployment, build)
    raise ValueError(f"Unsupported deployment format: {deployment.format}")
