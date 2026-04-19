"""Build status and log endpoints."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session, get_session_factory, init_engine
from factory.models.build import Build, BuildLog, BuildStatus
from factory.persistence import get_build, get_requirements, save_build
from factory.workers.pipeline_worker import run_pipeline

router = APIRouter(prefix="/builds", tags=["builds"])

_TERMINAL_BUILD_STATUSES = {
    BuildStatus.PASSED,
    BuildStatus.FAILED,
    BuildStatus.DEPLOYED,
}


def _ensure_session_factory():
    try:
        return get_session_factory()
    except RuntimeError:
        init_engine()
        return get_session_factory()


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


@router.get("/{build_id}/events")
async def get_build_events(
    build_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    return [log.model_dump(mode="json") for log in build.logs]


@router.get("/{build_id}/stream")
async def stream_build_events(build_id: UUID) -> StreamingResponse:
    session_factory = _ensure_session_factory()

    async def event_stream():
        sent_count = 0
        while True:
            async with session_factory() as session:
                build = await get_build(session, build_id)
            if build is None:
                yield "event: error\ndata: {\"detail\":\"not_found\"}\n\n"
                return

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
) -> Build:
    build = await get_build(session, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="not_found")
    if build.requirements_id is None:
        raise HTTPException(status_code=409, detail="requirements_missing")

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
