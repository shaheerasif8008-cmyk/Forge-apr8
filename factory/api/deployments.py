"""Deployment management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.deployment import Deployment
from factory.persistence import get_deployment

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("/{deployment_id}", response_model=Deployment)
async def get_deployment_by_id(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Deployment:
    """Get deployment status by deployment ID."""
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")
    return deployment
