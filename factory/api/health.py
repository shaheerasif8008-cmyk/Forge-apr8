"""Factory health, readiness, recovery, and meta-context endpoints."""

from __future__ import annotations

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from factory.auth import FactoryAuthContext, get_factory_auth
from factory.config import get_settings
from factory.database import get_db_session, get_engine, get_session_factory
from factory.models.client import ClientOrg
from factory.models.orm import BuildRow
from factory.persistence import list_client_orgs

router = APIRouter(tags=["meta"])


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


class DependencyStatus(BaseModel):
    name: str
    healthy: bool
    detail: str = ""


class ReadinessResponse(BaseModel):
    ready: bool
    dependencies: list[DependencyStatus]


class RecoveryResponse(BaseModel):
    interrupted_builds: int
    detail: str = ""


class FactoryContextResponse(BaseModel):
    subject: str
    roles: list[str]
    org_ids: list[UUID]
    default_org_id: UUID | None = None
    orgs: list[ClientOrg]


@router.get("/health", response_model=LivenessResponse, summary="Process liveness")
async def liveness() -> LivenessResponse:
    """Return 200 if the process is alive. This does not check dependencies."""
    return LivenessResponse(status="ok", service="forge-factory", version="0.2.0")


@router.get("/ready", response_model=ReadinessResponse, summary="Dependency readiness")
async def readiness(response: Response) -> ReadinessResponse:
    """Return dependency readiness for load-balancer and deployment gates."""
    settings = get_settings()
    deps: list[DependencyStatus] = []

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps.append(DependencyStatus(name="postgres", healthy=True))
    except Exception as exc:  # noqa: BLE001
        deps.append(DependencyStatus(name="postgres", healthy=False, detail=str(exc)))

    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        deps.append(DependencyStatus(name="redis", healthy=True))
    except Exception as exc:  # noqa: BLE001
        deps.append(DependencyStatus(name="redis", healthy=False, detail=str(exc)))

    ready = all(dep.healthy for dep in deps)
    if not ready:
        response.status_code = 503
    return ReadinessResponse(ready=ready, dependencies=deps)


@router.get("/recovery", response_model=RecoveryResponse, summary="Recovery state")
async def recovery() -> RecoveryResponse:
    """Return counts of factory work interrupted by the last restart."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(BuildRow).where(BuildRow.status == "interrupted"))
            interrupted = result.scalars().all()
        return RecoveryResponse(
            interrupted_builds=len(interrupted),
            detail=(
                f"interrupted build ids: {[str(build.id) for build in interrupted]}"
                if interrupted
                else ""
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return RecoveryResponse(interrupted_builds=-1, detail=f"recovery check failed: {exc}")


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
