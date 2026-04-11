"""Commission endpoints — start and inspect the factory pipeline for an employee."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.build import Build, BuildLog, BuildStatus
from factory.models.requirements import EmployeeRequirements
from factory.persistence import get_deployment_for_build, get_latest_build_for_commission, get_requirements, save_build, save_requirements
from factory.workers.pipeline_worker import run_pipeline

router = APIRouter(prefix="/commissions", tags=["commissions"])


class CommissionRequest(EmployeeRequirements):
    """Public intake form — same shape as EmployeeRequirements for now."""


class CommissionAcceptedResponse(BaseModel):
    commission_id: UUID
    build_id: UUID
    status: BuildStatus


class CommissionStatusResponse(BaseModel):
    commission_id: UUID
    build_id: UUID | None = None
    status: BuildStatus
    logs: list[BuildLog]
    deployment_id: UUID | None = None
    deployment_status: str = ""
    access_url: str = ""


class CommissionLogsResponse(BaseModel):
    commission_id: UUID
    build_id: UUID
    logs: list[BuildLog]


@router.post("/", response_model=CommissionAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_commission(
    payload: CommissionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CommissionAcceptedResponse:
    """Accept a new employee commission and queue the full factory pipeline."""
    requirements = EmployeeRequirements(**payload.model_dump())
    build = Build(
        requirements_id=requirements.id,
        org_id=requirements.org_id,
        status=BuildStatus.QUEUED,
        metadata={"requirements_id": str(requirements.id)},
    )
    await save_requirements(session, requirements)
    await save_build(session, build)
    run_pipeline.delay(requirements.model_dump(mode="json"), build.model_dump(mode="json"))
    return CommissionAcceptedResponse(
        commission_id=requirements.id,
        build_id=build.id,
        status=build.status,
    )


@router.get("/{commission_id}", response_model=CommissionStatusResponse)
async def get_commission(
    commission_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommissionStatusResponse:
    """Retrieve the latest build/deployment status for a commission."""
    requirements = await get_requirements(session, commission_id)
    if requirements is None:
        raise HTTPException(status_code=404, detail="not_found")

    build = await get_latest_build_for_commission(session, commission_id)
    if build is None:
        return CommissionStatusResponse(
            commission_id=commission_id,
            status=BuildStatus.QUEUED,
            logs=[],
        )

    deployment = await get_deployment_for_build(session, build.id)
    return CommissionStatusResponse(
        commission_id=commission_id,
        build_id=build.id,
        status=build.status,
        logs=build.logs,
        deployment_id=None if deployment is None else deployment.id,
        deployment_status="" if deployment is None else deployment.status.value,
        access_url="" if deployment is None else deployment.access_url,
    )


@router.get("/{commission_id}/logs", response_model=CommissionLogsResponse)
async def get_commission_logs(
    commission_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommissionLogsResponse:
    """Return build logs for the latest build associated with a commission."""
    build = await get_latest_build_for_commission(session, commission_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    return CommissionLogsResponse(commission_id=commission_id, build_id=build.id, logs=build.logs)
