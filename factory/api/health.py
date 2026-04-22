"""Health check endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from factory.auth import FactoryAuthContext, get_factory_auth
from factory.database import get_db_session
from factory.models.client import ClientOrg
from factory.persistence import list_client_orgs

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class FactoryContextResponse(BaseModel):
    subject: str
    roles: list[str]
    org_ids: list[UUID]
    default_org_id: UUID | None = None
    orgs: list[ClientOrg]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service liveness status."""
    return HealthResponse(status="ok", service="forge-factory", version="0.2.0")


@router.get("/context", response_model=FactoryContextResponse)
async def context(
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> FactoryContextResponse:
    org_ids = [UUID(org_id) for org_id in auth.org_ids]
    orgs = await list_client_orgs(session, org_ids)
    ordered_org_ids = [org.id for org in orgs]
    default_org_id = ordered_org_ids[0] if ordered_org_ids else (org_ids[0] if org_ids else None)
    return FactoryContextResponse(
        subject=auth.subject,
        roles=sorted(auth.roles),
        org_ids=ordered_org_ids or org_ids,
        default_org_id=default_org_id,
        orgs=orgs,
    )
