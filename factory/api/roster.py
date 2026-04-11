"""Client employee roster endpoints."""

from __future__ import annotations

import subprocess
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.deployment import Deployment, DeploymentStatus
from factory.persistence import get_deployment, list_deployments_for_org, save_deployment
from factory.pipeline.evaluator.container_runner import wait_for_health

router = APIRouter(prefix="/roster", tags=["roster"])


@router.get("/", response_model=list[Deployment])
async def list_employees(
    org_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[Deployment]:
    """Return all deployments for an org."""
    return await list_deployments_for_org(session, org_id)


@router.get("/{deployment_id}", response_model=Deployment)
async def get_employee(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Deployment:
    """Return deployment details for a single employee."""
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")
    return deployment


@router.post("/{deployment_id}/stop", response_model=Deployment)
async def stop_employee(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Deployment:
    """Stop a deployed employee container."""
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")

    container_id = str(deployment.infrastructure.get("container_id", ""))
    if not container_id:
        raise HTTPException(status_code=409, detail="missing_container_id")

    subprocess.run(["docker", "stop", container_id], capture_output=True, text=True, check=True)
    deployment.status = DeploymentStatus.INACTIVE
    return await save_deployment(session, deployment)


@router.post("/{deployment_id}/restart", response_model=Deployment)
async def restart_employee(
    deployment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Deployment:
    """Restart a deployed employee container and re-check health."""
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="not_found")

    container_id = str(deployment.infrastructure.get("container_id", ""))
    if not container_id:
        raise HTTPException(status_code=409, detail="missing_container_id")

    subprocess.run(["docker", "start", container_id], capture_output=True, text=True, check=True)
    healthy = await wait_for_health(f"{deployment.access_url}/health", timeout=60)
    deployment.status = DeploymentStatus.ACTIVE if healthy else DeploymentStatus.DEGRADED
    return await save_deployment(session, deployment)
