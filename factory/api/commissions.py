"""Commission endpoints — start the factory pipeline for a new employee."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException

from factory.models.requirements import EmployeeRequirements
from factory.models.build import Build, BuildStatus
from factory.pipeline.analyst.requirements_builder import build_requirements
from factory.workers.pipeline_worker import start_pipeline

router = APIRouter(prefix="/commissions", tags=["commissions"])


class CommissionRequest(EmployeeRequirements):
    """Public intake form — same shape as EmployeeRequirements for now."""


@router.post("/", response_model=Build, status_code=202)
async def create_commission(
    payload: CommissionRequest,
    background: BackgroundTasks,
) -> Build:
    """Accept a new employee commission and start the factory pipeline."""
    requirements = EmployeeRequirements(**payload.model_dump())
    build = Build(
        blueprint_id=requirements.id,  # overwritten after Architect runs
        org_id=requirements.org_id,
        status=BuildStatus.QUEUED,
    )
    background.add_task(start_pipeline, requirements, build)
    return build


@router.get("/{commission_id}", response_model=EmployeeRequirements)
async def get_commission(commission_id: UUID) -> EmployeeRequirements:
    """Retrieve a commission by ID (stub — will hit DB)."""
    raise HTTPException(status_code=404, detail="not_found")
