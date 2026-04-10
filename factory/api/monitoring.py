"""Employee health and metric endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from factory.models.monitoring import MonitoringEvent

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/{deployment_id}/events", response_model=list[MonitoringEvent])
async def list_events(deployment_id: UUID) -> list[MonitoringEvent]:
    """List monitoring events for a deployment (stub)."""
    return []
