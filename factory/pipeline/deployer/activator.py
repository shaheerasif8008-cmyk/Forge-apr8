"""Activator: connects integrations and activates the deployed employee."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import structlog

from factory.models.deployment import Deployment, DeploymentStatus
from factory.pipeline.deployer.connector import Connector, all_integrations_connected
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
    healthy = await wait_for_health(f"{deployment.access_url}/api/v1/health", timeout=60)
    if not healthy:
        deployment.status = DeploymentStatus.DEGRADED
        logger.warning("activator_unhealthy", deployment_id=str(deployment.id))
        return deployment

    connector = Connector()
    if deployment.integrations:
        deadline = asyncio.get_event_loop().time() + 3600
        while asyncio.get_event_loop().time() < deadline:
            deployment = await connector.refresh_statuses(deployment)
            if all_integrations_connected(deployment):
                break
            await asyncio.sleep(0.01)

        if not all_integrations_connected(deployment):
            deployment.status = DeploymentStatus.PENDING_CLIENT_ACTION
            logger.warning("activator_waiting_for_client_action", deployment_id=str(deployment.id))
            return deployment

    deployment.status = DeploymentStatus.ACTIVE
    deployment.activated_at = datetime.now(UTC)
    deployment.recovery_policy = {
        "health_endpoint": "/api/v1/health",
        "recovery_endpoint": "/api/v1/runtime/recovery",
        **dict(deployment.recovery_policy),
    }
    recovery_payload: dict[str, object] = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{deployment.access_url}/api/v1/runtime/recovery")
            if response.status_code == 200:
                recovery_payload = dict(response.json())
    except httpx.HTTPError:
        recovery_payload = {}
    deployment.recovery_state = {
        "restart_count": int(deployment.recovery_state.get("restart_count", 0)),
        "last_restarted_at": deployment.recovery_state.get("last_restarted_at"),
        "last_runtime_recovery": recovery_payload,
    }
    logger.info("activator_complete", access_url=deployment.access_url)
    return deployment
