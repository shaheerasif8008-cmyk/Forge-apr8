"""Build status and log endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from factory.models.build import Build

router = APIRouter(prefix="/builds", tags=["builds"])


@router.get("/{build_id}", response_model=Build)
async def get_build(build_id: UUID) -> Build:
    """Retrieve build status and logs by build ID (stub — will hit DB)."""
    raise HTTPException(status_code=404, detail="not_found")
