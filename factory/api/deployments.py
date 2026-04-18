"""Deployment management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.deployment import Deployment
from factory.persistence import get_deployment, save_deployment
from factory.pipeline.deployer.connector import Connector, pending_oauth_urls

router = APIRouter(prefix="/deployments", tags=["deployments"])


class IntegrationCallbackPayload(BaseModel):
    tool_id: str
    provider: str | None = None
    composio_connection_id: str | None = None
    status: str = "connected"


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


@router.get("/{deployment_id}/integrations/urls")
async def get_integration_urls(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, str]]:
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")
    return pending_oauth_urls(deployment)


@router.post("/{deployment_id}/integrations/callback", response_model=Deployment)
async def handle_integration_callback(
    deployment_id: UUID,
    payload: IntegrationCallbackPayload,
    session: AsyncSession = Depends(get_db_session),
) -> Deployment:
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")
    connector = Connector()
    deployment = await connector.handle_callback(
        deployment,
        tool_id=payload.tool_id,
        connection_id=payload.composio_connection_id,
        provider=payload.provider,
        status=payload.status,
    )
    return await save_deployment(session, deployment)
