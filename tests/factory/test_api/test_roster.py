"""Tests for roster API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from factory.database import get_db_session
from factory.main import app
from factory.models.deployment import Deployment, DeploymentStatus


@pytest.mark.anyio
async def test_list_roster_for_org(client: AsyncClient, sample_org, monkeypatch) -> None:
    async def fake_db():
        yield object()

    deployments = [
        Deployment(build_id=sample_org.id, org_id=sample_org.id, status=DeploymentStatus.ACTIVE),
    ]

    app.dependency_overrides[get_db_session] = fake_db
    async def fake_list(session, org_id):
        return deployments

    monkeypatch.setattr("factory.api.roster.list_deployments_for_org", fake_list)

    response = await client.get(f"/api/v1/roster?org_id={sample_org.id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.anyio
async def test_rollback_employee(client: AsyncClient, sample_org, monkeypatch) -> None:
    async def fake_db():
        yield object()

    deployment = Deployment(build_id=sample_org.id, org_id=sample_org.id, status=DeploymentStatus.ACTIVE)

    async def fake_get(session, deployment_id):
        return deployment

    async def fake_rollback(deployment_to_rollback, session=None):
        deployment_to_rollback.status = DeploymentStatus.ROLLED_BACK
        return deployment_to_rollback

    async def fake_save(session, next_deployment):
        return next_deployment

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.roster.get_deployment", fake_get)
    monkeypatch.setattr("factory.api.roster.rollback", fake_rollback)
    monkeypatch.setattr("factory.api.roster.save_deployment", fake_save)

    response = await client.post(f"/api/v1/roster/{deployment.id}/rollback")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "rolled_back"
