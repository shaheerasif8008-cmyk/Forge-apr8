"""Rollback helpers for failed deployments."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from factory.models.deployment import Deployment, DeploymentStatus
from factory.models.monitoring import EventSeverity, MonitoringEvent
from factory.persistence import save_monitoring_event
from factory.pipeline.deployer.connector import Connector
from factory.pipeline.evaluator.container_runner import stop_container


async def rollback(deployment: Deployment, session: AsyncSession | None = None) -> Deployment:
    infrastructure = deployment.infrastructure if isinstance(deployment.infrastructure, dict) else {}
    container_id = str(infrastructure.get("container_id", "")).strip()
    if container_id:
        await stop_container(container_id)

    connector = Connector()
    await connector.delete_connections(deployment)

    deployment.status = DeploymentStatus.ROLLED_BACK
    deployment.access_url = ""
    deployment.infrastructure = {}

    if session is not None:
        event = MonitoringEvent(
            deployment_id=deployment.id,
            org_id=deployment.org_id,
            severity=EventSeverity.ERROR,
            category="deployment",
            title="Deployment rolled back",
            detail={"reason": "deployment_failure", "integration_count": len(deployment.integrations)},
        )
        await save_monitoring_event(session, event)

    return deployment
