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
