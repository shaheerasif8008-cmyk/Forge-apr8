"""Tests for commission API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from factory.database import get_db_session
from factory.main import app
from factory.models.build import Build, BuildLog, BuildStatus
from factory.models.deployment import Deployment, DeploymentStatus


@pytest.mark.anyio
async def test_create_commission_queues_pipeline(client: AsyncClient, sample_requirements, monkeypatch) -> None:
    async def fake_db():
        yield object()

    recorded: dict[str, object] = {}

    async def fake_save_requirements(session, requirements):
        recorded["requirements"] = requirements
        return requirements

    async def fake_save_build(session, build):
        recorded["build"] = build
        return build

    def fake_delay(requirements_dict, build_dict):
        recorded["queued"] = (requirements_dict, build_dict)

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.commissions.save_requirements", fake_save_requirements)
    monkeypatch.setattr("factory.api.commissions.save_build", fake_save_build)
    monkeypatch.setattr("factory.api.commissions.run_pipeline.delay", fake_delay)

    response = await client.post("/api/v1/commissions", json=sample_requirements.model_dump(mode="json"))
    app.dependency_overrides.clear()

    assert response.status_code == 202
    data = response.json()
    assert data["commission_id"] == str(sample_requirements.id)
    assert "queued" in recorded


@pytest.mark.anyio
async def test_get_commission_returns_status_summary(client: AsyncClient, sample_requirements, sample_build, monkeypatch) -> None:
    async def fake_db():
        yield object()

    sample_build.status = BuildStatus.DEPLOYED
    sample_build.logs = [BuildLog(stage="assembler", message="done")]
    deployment = Deployment(
        build_id=sample_build.id,
        org_id=sample_build.org_id,
        status=DeploymentStatus.ACTIVE,
        access_url="http://127.0.0.1:9001",
    )

    app.dependency_overrides[get_db_session] = fake_db
    async def fake_get_requirements(session, commission_id):
        return sample_requirements

    async def fake_get_build(session, commission_id):
        return sample_build

    async def fake_get_deployment(session, build_id):
        return deployment

    monkeypatch.setattr("factory.api.commissions.get_requirements", fake_get_requirements)
    monkeypatch.setattr("factory.api.commissions.get_latest_build_for_commission", fake_get_build)
    monkeypatch.setattr("factory.api.commissions.get_deployment_for_build", fake_get_deployment)

    response = await client.get(f"/api/v1/commissions/{sample_requirements.id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deployed"
    assert data["access_url"] == "http://127.0.0.1:9001"
