"""Client employee roster endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from factory.models.deployment import Deployment

router = APIRouter(prefix="/roster", tags=["roster"])


@router.get("/{org_id}", response_model=list[Deployment])
async def list_employees(org_id: UUID) -> list[Deployment]:
    """Return all active deployments for an org (stub)."""
    return []
