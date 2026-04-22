"""Employee health and metric endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from factory.auth import FactoryAuthContext, ensure_org_access, get_factory_auth
from factory.database import get_db_session
from factory.models.monitoring import MonitoringEvent
from factory.persistence import get_deployment, list_monitoring_events, list_performance_metrics

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/{deployment_id}/events", response_model=list[MonitoringEvent])
async def list_events(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> list[MonitoringEvent]:
    """List monitoring events for a deployment."""
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        return []
    ensure_org_access(auth, deployment.org_id)
    return await list_monitoring_events(session, deployment_id)


@router.get("/{deployment_id}/metrics")
async def list_metrics(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> list[dict]:
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        return []
    ensure_org_access(auth, deployment.org_id)
    metrics = await list_performance_metrics(session, deployment_id)
    return [metric.model_dump(mode="json") for metric in metrics]
