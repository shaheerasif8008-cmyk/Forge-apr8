"""Build status and log endpoints."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from factory.auth import FactoryAuthContext, ensure_org_access, get_factory_auth
from factory.database import get_db_session, get_session_factory, init_engine
from factory.models.build import Build, BuildLog, BuildStatus
from factory.persistence import get_build, get_requirements, list_builds_for_org, save_build
from factory.workers.pipeline_worker import resume_deployment_task, run_pipeline

router = APIRouter(prefix="/builds", tags=["builds"])

_TERMINAL_BUILD_STATUSES = {
    BuildStatus.PASSED,
    BuildStatus.PENDING_REVIEW,
    BuildStatus.PENDING_CLIENT_ACTION,
    BuildStatus.FAILED,
    BuildStatus.DEPLOYED,
}


def _ensure_session_factory():
    try:
        return get_session_factory()
    except RuntimeError:
        init_engine()
        return get_session_factory()


@router.get("", response_model=list[Build])
async def list_builds(
    org_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> list[Build]:
    ensure_org_access(auth, org_id)
    return await list_builds_for_org(session, org_id)


@router.get("/{build_id}", response_model=Build)
async def get_build_by_id(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> Build:
    """Retrieve build status and logs by build ID."""
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    ensure_org_access(auth, build.org_id)
    return build


@router.get("/{build_id}/events")
async def get_build_events(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> list[dict]:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    ensure_org_access(auth, build.org_id)
    return [log.model_dump(mode="json") for log in build.logs]


@router.get("/{build_id}/stream")
async def stream_build_events(
    build_id: UUID,
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> StreamingResponse:
    session_factory = _ensure_session_factory()

    async def event_stream():
        sent_count = 0
        while True:
            async with session_factory() as session:
                build = await get_build(session, build_id)
            if build is None:
                yield "event: error\ndata: {\"detail\":\"not_found\"}\n\n"
                return
            ensure_org_access(auth, build.org_id)

            payload = {
                "build_id": str(build.id),
                "status": build.status.value,
                "iteration": build.iteration,
                "logs": [log.model_dump(mode="json") for log in build.logs[sent_count:]],
            }
            yield f"event: build\ndata: {json.dumps(payload)}\n\n"
            sent_count = len(build.logs)
            if build.status in _TERMINAL_BUILD_STATUSES:
                return
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{build_id}/retry", response_model=Build)
async def retry_build(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> Build:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    ensure_org_access(auth, build.org_id)
    if build.requirements_id is None:
        raise HTTPException(status_code=409, detail="requirements_missing")
    if build.status not in {BuildStatus.FAILED}:
        raise HTTPException(status_code=409, detail="build_not_retryable")

    requirements = await get_requirements(session, build.requirements_id)
    if requirements is None:
        raise HTTPException(status_code=404, detail="requirements_not_found")

    build.status = BuildStatus.QUEUED
    build.completed_at = None
    build.iteration += 1
    build.logs.append(
        BuildLog(
            stage="retry",
            message="Retry requested from factory portal.",
            detail={"requested_build_id": str(build.id)},
        )
    )
    build = await save_build(session, build)
    run_pipeline.delay(requirements.model_dump(mode="json"), build.model_dump(mode="json"))
    return build


@router.post("/{build_id}/approve", response_model=Build)
async def approve_build(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> Build:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    ensure_org_access(auth, build.org_id)
    if build.status != BuildStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="build_not_pending_review")

    resume_deployment_task.delay(str(build.id))
    build.logs.append(
        BuildLog(
            stage="review",
            message="Human review approved. Deployment has been queued.",
            detail={"build_id": str(build.id)},
        )
    )
    build.status = BuildStatus.DEPLOYING
    build.completed_at = None
    build = await save_build(session, build)
    return build


@router.post("/{build_id}/reject", response_model=Build)
async def reject_build(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> Build:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    ensure_org_access(auth, build.org_id)
    if build.status != BuildStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="build_not_pending_review")

    build.status = BuildStatus.FAILED
    build.logs.append(
        BuildLog(
            stage="review",
            level="warning",
            message="Human review rejected the build before deployment.",
            detail={"build_id": str(build.id)},
        )
    )
    build.completed_at = datetime.now(UTC)
    build = await save_build(session, build)
    return build
