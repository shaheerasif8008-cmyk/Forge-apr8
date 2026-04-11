"""Build status and log endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.build import Build
from factory.persistence import get_build

router = APIRouter(prefix="/builds", tags=["builds"])


@router.get("/{build_id}", response_model=Build)
async def get_build_by_id(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Build:
    """Retrieve build status and logs by build ID."""
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    return build
