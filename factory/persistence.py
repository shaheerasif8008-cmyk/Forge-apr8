"""Persistence helpers for Forge factory Pydantic models."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build
from factory.models.deployment import Deployment
from factory.models.orm import BlueprintRow, BuildRow, DeploymentRow, EmployeeRequirementsRow
from factory.models.requirements import EmployeeRequirements


def _dump_items(items: Iterable[Any]) -> list[dict[str, Any]]:
    dumped: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            dumped.append(item.model_dump(mode="json"))
        else:
            dumped.append(dict(item))
    return dumped


def _set_attrs(row: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(row, key, value)


def requirements_to_row_payload(requirements: EmployeeRequirements) -> dict[str, Any]:
    return requirements.model_dump()


def blueprint_to_row_payload(blueprint: EmployeeBlueprint) -> dict[str, Any]:
    payload = blueprint.model_dump()
    payload["components"] = _dump_items(blueprint.components)
    payload["custom_code_specs"] = _dump_items(blueprint.custom_code_specs)
    return payload


def build_to_row_payload(build: Build) -> dict[str, Any]:
    payload = build.model_dump()
    payload["logs"] = _dump_items(build.logs)
    payload["artifacts"] = _dump_items(build.artifacts)
    payload["status"] = build.status.value
    return payload


def deployment_to_row_payload(deployment: Deployment) -> dict[str, Any]:
    payload = deployment.model_dump()
    payload["format"] = deployment.format.value
    payload["status"] = deployment.status.value
    return payload


def requirements_from_row(row: EmployeeRequirementsRow) -> EmployeeRequirements:
    return EmployeeRequirements.model_validate(
        {
            "id": row.id,
            "org_id": row.org_id,
            "name": row.name,
            "role_summary": row.role_summary,
            "primary_responsibilities": row.primary_responsibilities,
            "kpis": row.kpis,
            "required_tools": row.required_tools,
            "required_data_sources": row.required_data_sources,
            "communication_channels": row.communication_channels,
            "compliance_frameworks": row.compliance_frameworks,
            "risk_tier": row.risk_tier,
            "deployment_format": row.deployment_format,
            "supervisor_email": row.supervisor_email,
            "org_context": row.org_context,
            "raw_intake": row.raw_intake,
            "created_at": row.created_at,
        }
    )


def blueprint_from_row(row: BlueprintRow) -> EmployeeBlueprint:
    return EmployeeBlueprint.model_validate(
        {
            "id": row.id,
            "requirements_id": row.requirements_id,
            "org_id": row.org_id,
            "employee_name": row.employee_name,
            "components": row.components,
            "custom_code_specs": row.custom_code_specs,
            "workflow_description": row.workflow_description,
            "autonomy_profile": row.autonomy_profile,
            "estimated_cost_per_task_usd": row.estimated_cost_per_task_usd,
            "architect_reasoning": row.architect_reasoning,
            "created_at": row.created_at,
        }
    )


def build_from_row(row: BuildRow) -> Build:
    return Build.model_validate(
        {
            "id": row.id,
            "requirements_id": row.requirements_id,
            "blueprint_id": row.blueprint_id,
            "org_id": row.org_id,
            "status": row.status,
            "iteration": row.iteration,
            "logs": row.logs,
            "artifacts": row.artifacts,
            "test_report": row.test_report,
            "metadata": row.metadata,
            "created_at": row.created_at,
            "completed_at": row.completed_at,
        }
    )


def deployment_from_row(row: DeploymentRow) -> Deployment:
    return Deployment.model_validate(
        {
            "id": row.id,
            "build_id": row.build_id,
            "org_id": row.org_id,
            "format": row.format,
            "status": row.status,
            "access_url": row.access_url,
            "infrastructure": row.infrastructure,
            "health_last_checked": row.health_last_checked,
            "created_at": row.created_at,
            "activated_at": row.activated_at,
        }
    )


async def save_requirements(session: AsyncSession, requirements: EmployeeRequirements) -> EmployeeRequirements:
    row = await session.get(EmployeeRequirementsRow, requirements.id)
    payload = requirements_to_row_payload(requirements)
    if row is None:
        row = EmployeeRequirementsRow(**payload)
        session.add(row)
    else:
        _set_attrs(row, payload)
    await session.flush()
    return requirements_from_row(row)


async def save_blueprint(session: AsyncSession, blueprint: EmployeeBlueprint) -> EmployeeBlueprint:
    row = await session.get(BlueprintRow, blueprint.id)
    payload = blueprint_to_row_payload(blueprint)
    if row is None:
        row = BlueprintRow(**payload)
        session.add(row)
    else:
        _set_attrs(row, payload)
    await session.flush()
    return blueprint_from_row(row)


async def save_build(session: AsyncSession, build: Build) -> Build:
    row = await session.get(BuildRow, build.id)
    payload = build_to_row_payload(build)
    if row is None:
        row = BuildRow(**payload)
        session.add(row)
    else:
        _set_attrs(row, payload)
    await session.flush()
    return build_from_row(row)


async def save_deployment(session: AsyncSession, deployment: Deployment) -> Deployment:
    row = await session.get(DeploymentRow, deployment.id)
    payload = deployment_to_row_payload(deployment)
    if row is None:
        row = DeploymentRow(**payload)
        session.add(row)
    else:
        _set_attrs(row, payload)
    await session.flush()
    return deployment_from_row(row)


async def get_requirements(session: AsyncSession, requirements_id: UUID) -> EmployeeRequirements | None:
    row = await session.get(EmployeeRequirementsRow, requirements_id)
    return None if row is None else requirements_from_row(row)


async def get_blueprint(session: AsyncSession, blueprint_id: UUID) -> EmployeeBlueprint | None:
    row = await session.get(BlueprintRow, blueprint_id)
    return None if row is None else blueprint_from_row(row)


async def get_build(session: AsyncSession, build_id: UUID) -> Build | None:
    row = await session.get(BuildRow, build_id)
    return None if row is None else build_from_row(row)


async def get_deployment(session: AsyncSession, deployment_id: UUID) -> Deployment | None:
    row = await session.get(DeploymentRow, deployment_id)
    return None if row is None else deployment_from_row(row)


async def get_deployment_for_build(session: AsyncSession, build_id: UUID) -> Deployment | None:
    statement = select(DeploymentRow).where(DeploymentRow.build_id == build_id)
    row = (await session.execute(statement)).scalar_one_or_none()
    return None if row is None else deployment_from_row(row)


async def get_latest_build_for_commission(
    session: AsyncSession,
    commission_id: UUID,
) -> Build | None:
    statement: Select[tuple[BuildRow]] = (
        select(BuildRow)
        .where(BuildRow.requirements_id == commission_id)
        .order_by(desc(BuildRow.created_at))
        .limit(1)
    )
    row = (await session.execute(statement)).scalar_one_or_none()
    return None if row is None else build_from_row(row)


async def list_deployments_for_org(session: AsyncSession, org_id: UUID) -> list[Deployment]:
    statement = (
        select(DeploymentRow)
        .where(DeploymentRow.org_id == org_id)
        .order_by(desc(DeploymentRow.created_at))
    )
    rows = (await session.execute(statement)).scalars().all()
    return [deployment_from_row(row) for row in rows]
