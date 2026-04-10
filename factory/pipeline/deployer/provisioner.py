"""Provisioner: spins up cloud/server infrastructure for the employee."""

from __future__ import annotations

import structlog

from factory.models.deployment import Deployment, DeploymentStatus

logger = structlog.get_logger(__name__)


async def provision(deployment: Deployment) -> Deployment:
    """Provision infrastructure for the employee package.

    Args:
        deployment: Deployment record with format and build reference.

    Returns:
        Updated Deployment with infrastructure details.
    """
    deployment.status = DeploymentStatus.PROVISIONING
    logger.info("provisioner_start", deployment_id=str(deployment.id), format=deployment.format)
    # TODO: integrate with Railway / AWS / Docker based on deployment.format
    deployment.infrastructure = {"provider": "railway", "region": "us-east-1"}
    return deployment
