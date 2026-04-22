"""Health checker: polls employee endpoints and records status."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from factory.models.deployment import Deployment, DeploymentStatus
from factory.models.monitoring import EventSeverity, MonitoringEvent

logger = structlog.get_logger(__name__)


async def check_health(deployment: Deployment) -> MonitoringEvent:
    """Ping the employee health endpoint and return a MonitoringEvent.

    Args:
        deployment: Active deployment to check.

    Returns:
        MonitoringEvent with current health status.
    """
    deployment.health_last_checked = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{deployment.access_url}/api/v1/health")
        ok = resp.status_code == 200
        severity = EventSeverity.INFO if ok else EventSeverity.ERROR
        title = "health_ok" if ok else f"health_failed_status_{resp.status_code}"
        if ok:
            deployment.status = DeploymentStatus.ACTIVE
        else:
            deployment.status = DeploymentStatus.DEGRADED
    except httpx.RequestError as exc:
        severity = EventSeverity.CRITICAL
        title = f"health_unreachable: {exc}"
        deployment.status = DeploymentStatus.DEGRADED

    return MonitoringEvent(
        deployment_id=deployment.id,
        org_id=deployment.org_id,
        severity=severity,
        category="health",
        title=title,
    )
