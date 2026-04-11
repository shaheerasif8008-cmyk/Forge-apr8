"""Activator: connects integrations and activates the deployed employee."""

from __future__ import annotations

from datetime import datetime

import structlog

from factory.models.deployment import Deployment, DeploymentStatus
from factory.pipeline.evaluator.container_runner import wait_for_health

logger = structlog.get_logger(__name__)


async def activate(deployment: Deployment) -> Deployment:
    """Start the employee and confirm it is responding.

    Args:
        deployment: Provisioned and connected deployment.

    Returns:
        Deployment with ACTIVE status and access_url set.
    """
    deployment.status = DeploymentStatus.ACTIVATING
    logger.info("activator_start", deployment_id=str(deployment.id))
    healthy = await wait_for_health(f"{deployment.access_url}/health", timeout=60)
    if not healthy:
        deployment.status = DeploymentStatus.DEGRADED
        logger.warning("activator_unhealthy", deployment_id=str(deployment.id))
        return deployment

    deployment.status = DeploymentStatus.ACTIVE
    deployment.activated_at = datetime.utcnow()
    logger.info("activator_complete", access_url=deployment.access_url)
    return deployment
