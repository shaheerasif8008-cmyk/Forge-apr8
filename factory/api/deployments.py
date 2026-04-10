"""Deployment management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from factory.models.deployment import Deployment

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("/{deployment_id}", response_model=Deployment)
async def get_deployment(deployment_id: UUID) -> Deployment:
    """Get deployment status (stub — will hit DB)."""
    raise HTTPException(status_code=404, detail="not_found")
