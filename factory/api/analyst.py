"""Analyst intake session and blueprint-preview endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from factory.auth import FactoryAuthContext, ensure_org_access, get_factory_auth
from factory.database import get_db_session
from factory.models.build import Build, BuildStatus
from factory.models.requirements import EmployeeRequirements
from factory.persistence import save_build, save_requirements
from factory.pipeline.analyst.conversation import (
    AnalystSession,
    append_message,
    start_session,
)
from factory.pipeline.analyst.requirements_builder import (
    build_requirements,
    build_requirements_from_state,
)
from factory.pipeline.architect.designer import design_employee
from factory.workers.pipeline_worker import run_pipeline

router = APIRouter(prefix="/analyst", tags=["analyst"])
logger = structlog.get_logger(__name__)

_SESSIONS: dict[str, AnalystSession] = {}


class AnalystSessionCreateRequest(BaseModel):
    org_id: UUID
    prompt: str


class AnalystMessageRequest(BaseModel):
    role: str = "user"
    content: str


class AnalystSessionResponse(BaseModel):
    session_id: str
    employee_type: str
    risk_tier: str
    clarifying_questions: list[str]
    transcript: list[dict[str, str]]
    next_question: str = ""
    completeness_score: float = 0.0
    is_complete: bool = False
    requirements_id: str = ""
    timed_out: bool = False


class BlueprintPreviewRequest(BaseModel):
    requirements: EmployeeRequirements


@router.post("/sessions", response_model=AnalystSessionResponse)
async def create_session(
    payload: AnalystSessionCreateRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> AnalystSessionResponse:
    ensure_org_access(auth, payload.org_id)
    session = await start_session(str(uuid4()), payload.prompt, str(payload.org_id))
    _SESSIONS[session.session_id] = session
    return AnalystSessionResponse(
        session_id=session.session_id,
        employee_type=session.inferred_employee_type.value,
        risk_tier=session.suggested_risk_tier.value,
        clarifying_questions=session.clarifying_questions,
        transcript=session.raw_messages,
        next_question=session.state.next_question if session.state else "",
        completeness_score=session.state.completeness_score if session.state else 0.0,
        is_complete=session.state.is_complete if session.state else False,
    )


@router.post("/sessions/{session_id}/messages", response_model=AnalystSessionResponse)
async def add_message(
    session_id: str,
    payload: AnalystMessageRequest,
    session_db: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> AnalystSessionResponse:
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail="session_not_found")
    ensure_org_access(auth, _SESSIONS[session_id].org_id)
    session = await append_message(_SESSIONS[session_id], payload.role, payload.content)
    requirements_id = ""
    if session.state and session.state.is_complete and not session.completed_requirements_id:
        requirements = await build_requirements_from_state(session.state)
        requirements = await save_requirements(session_db, requirements)
        session.completed_requirements_id = str(requirements.id)
        session.requirements_payload = requirements.model_dump(mode="json")
        requirements_id = session.completed_requirements_id
        logger.info("commission_created", session_id=session_id, requirements_id=requirements_id)
    return AnalystSessionResponse(
        session_id=session.session_id,
        employee_type=session.inferred_employee_type.value,
        risk_tier=session.suggested_risk_tier.value,
        clarifying_questions=session.clarifying_questions,
        transcript=session.raw_messages,
        next_question=session.state.next_question if session.state else "",
        completeness_score=session.state.completeness_score if session.state else 0.0,
        is_complete=session.state.is_complete if session.state else False,
        requirements_id=requirements_id or session.completed_requirements_id,
        timed_out=bool(session.state and getattr(session.state, "timed_out", False)),
    )


@router.get("/sessions/{session_id}", response_model=AnalystSessionResponse)
async def get_session(
    session_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> AnalystSessionResponse:
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail="session_not_found")
    session = _SESSIONS[session_id]
    ensure_org_access(auth, session.org_id)
    return AnalystSessionResponse(
        session_id=session.session_id,
        employee_type=session.inferred_employee_type.value,
        risk_tier=session.suggested_risk_tier.value,
        clarifying_questions=session.clarifying_questions,
        transcript=session.raw_messages,
        next_question=session.state.next_question if session.state else "",
        completeness_score=session.state.completeness_score if session.state else 0.0,
        is_complete=session.state.is_complete if session.state else False,
        requirements_id=session.completed_requirements_id,
        timed_out=bool(session.state and getattr(session.state, "timed_out", False)),
    )


@router.post("/sessions/{session_id}/requirements", response_model=EmployeeRequirements)
async def finalize_requirements(
    session_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> EmployeeRequirements:
    session = _SESSIONS[session_id]
    ensure_org_access(auth, session.org_id)
    if session.state is not None:
        return await build_requirements_from_state(session.state)
    raw_intake = "\n".join(message["content"] for message in session.raw_messages if message["role"] == "user")
    return await build_requirements(raw_intake, session.org_id)


@router.post("/blueprint-preview")
async def blueprint_preview(
    payload: BlueprintPreviewRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> dict:
    ensure_org_access(auth, payload.requirements.org_id)
    blueprint = await design_employee(payload.requirements)
    return blueprint.model_dump(mode="json")


@router.post("/sessions/{session_id}/commission")
async def commission_from_session(
    session_id: str,
    org_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    auth: FactoryAuthContext = Depends(get_factory_auth),
) -> dict[str, str]:
    analyst_session = _SESSIONS[session_id]
    ensure_org_access(auth, org_id or analyst_session.org_id)
    raw_intake = "\n".join(message["content"] for message in analyst_session.raw_messages if message["role"] == "user")
    requirements = await build_requirements(raw_intake, str(org_id or analyst_session.org_id))
    build = Build(
        requirements_id=requirements.id,
        org_id=requirements.org_id,
        status=BuildStatus.QUEUED,
        metadata={"requirements_id": str(requirements.id), "source_session_id": session_id},
    )
    await save_requirements(session, requirements)
    await save_build(session, build)
    run_pipeline.delay(requirements.model_dump(mode="json"), build.model_dump(mode="json"))
    return {"commission_id": str(requirements.id), "build_id": str(build.id)}
