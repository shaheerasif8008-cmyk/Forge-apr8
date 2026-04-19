"""Tests for build API endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from factory.database import get_db_session
from factory.main import app
from factory.models.build import BuildLog, BuildStatus


@pytest.mark.anyio
async def test_retry_build_requeues_pipeline(client, sample_requirements, sample_build, monkeypatch) -> None:
    async def fake_db():
        yield object()

    sample_build.status = BuildStatus.FAILED
    sample_build.logs = [BuildLog(stage="generator", message="failed once")]
    recorded: dict[str, object] = {}

    async def fake_get_build(session, build_id):
      return sample_build

    async def fake_get_requirements(session, requirements_id):
      return sample_requirements

    async def fake_save_build(session, build):
      recorded["build"] = build
      return build

    def fake_delay(requirements_dict, build_dict):
      recorded["queued"] = (requirements_dict, build_dict)

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.builds.get_build", fake_get_build)
    monkeypatch.setattr("factory.api.builds.get_requirements", fake_get_requirements)
    monkeypatch.setattr("factory.api.builds.save_build", fake_save_build)
    monkeypatch.setattr("factory.api.builds.run_pipeline.delay", fake_delay)

    response = await client.post(f"/api/v1/builds/{sample_build.id}/retry")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["iteration"] == 2
    assert "queued" in recorded


@pytest.mark.anyio
async def test_build_stream_returns_sse_payload(client, sample_build, monkeypatch) -> None:
    sample_build.status = BuildStatus.DEPLOYED
    sample_build.logs = [BuildLog(stage="packager", message="artifact ready")]

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fake_get_build(session, build_id):
        return sample_build

    monkeypatch.setattr("factory.api.builds._ensure_session_factory", lambda: fake_session)
    monkeypatch.setattr("factory.api.builds.get_build", fake_get_build)

    response = await client.get(f"/api/v1/builds/{sample_build.id}/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: build" in response.text
    assert "\"status\": \"deployed\"" in response.text
