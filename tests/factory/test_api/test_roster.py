"""Tests for roster API endpoints."""

from __future__ import annotations

from types import SimpleNamespace

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


@pytest.mark.anyio
async def test_restart_employee_records_runtime_recovery(client: AsyncClient, sample_org, monkeypatch) -> None:
    async def fake_db():
        yield object()

    deployment = Deployment(
        build_id=sample_org.id,
        org_id=sample_org.id,
        status=DeploymentStatus.INACTIVE,
        access_url="http://127.0.0.1:8123",
        infrastructure={"container_id": "container-1"},
    )

    async def fake_get(session, deployment_id):
        return deployment

    async def fake_save(session, next_deployment):
        return next_deployment

    async def fake_wait_for_health(url, timeout=60):
        assert url == "http://127.0.0.1:8123/api/v1/health"
        return True

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url):
            assert url == "http://127.0.0.1:8123/api/v1/runtime/recovery"
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"startup_summary": {"interrupted_task_ids": ["task-1"]}},
            )

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.roster.get_deployment", fake_get)
    monkeypatch.setattr("factory.api.roster.save_deployment", fake_save)
    monkeypatch.setattr("factory.api.roster.wait_for_health", fake_wait_for_health)
    monkeypatch.setattr("factory.api.roster.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        "factory.api.roster.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="started", stderr=""),
    )

    response = await client.post(f"/api/v1/roster/{deployment.id}/restart")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["recovery_state"]["restart_count"] == 1
    assert payload["recovery_state"]["last_runtime_recovery"]["startup_summary"]["interrupted_task_ids"] == ["task-1"]
