"""Analyst intake session and blueprint-preview endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from factory.database import get_db_session
from factory.models.build import Build, BuildStatus
from factory.models.requirements import EmployeeRequirements
from factory.persistence import save_build, save_requirements
from factory.pipeline.analyst.conversation import AnalystSession, append_message, start_session
from factory.pipeline.analyst.requirements_builder import build_requirements
from factory.pipeline.architect.designer import design_employee
from factory.workers.pipeline_worker import run_pipeline

router = APIRouter(prefix="/analyst", tags=["analyst"])

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


class BlueprintPreviewRequest(BaseModel):
    requirements: EmployeeRequirements


@router.post("/sessions", response_model=AnalystSessionResponse)
async def create_session(payload: AnalystSessionCreateRequest) -> AnalystSessionResponse:
    session = start_session(str(uuid4()), payload.prompt, str(payload.org_id))
    _SESSIONS[session.session_id] = session
    return AnalystSessionResponse(
        session_id=session.session_id,
        employee_type=session.inferred_employee_type.value,
        risk_tier=session.suggested_risk_tier.value,
        clarifying_questions=session.clarifying_questions,
        transcript=session.raw_messages,
    )


@router.post("/sessions/{session_id}/messages", response_model=AnalystSessionResponse)
async def add_message(session_id: str, payload: AnalystMessageRequest) -> AnalystSessionResponse:
    session = append_message(_SESSIONS[session_id], payload.role, payload.content)
    return AnalystSessionResponse(
        session_id=session.session_id,
        employee_type=session.inferred_employee_type.value,
        risk_tier=session.suggested_risk_tier.value,
        clarifying_questions=session.clarifying_questions,
        transcript=session.raw_messages,
    )


@router.post("/sessions/{session_id}/requirements", response_model=EmployeeRequirements)
async def finalize_requirements(session_id: str) -> EmployeeRequirements:
    session = _SESSIONS[session_id]
    raw_intake = "\n".join(message["content"] for message in session.raw_messages if message["role"] == "user")
    return await build_requirements(raw_intake, session.org_id)


@router.post("/blueprint-preview")
async def blueprint_preview(payload: BlueprintPreviewRequest) -> dict:
    blueprint = await design_employee(payload.requirements)
    return blueprint.model_dump(mode="json")


@router.post("/sessions/{session_id}/commission")
async def commission_from_session(
    session_id: str,
    org_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    analyst_session = _SESSIONS[session_id]
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
