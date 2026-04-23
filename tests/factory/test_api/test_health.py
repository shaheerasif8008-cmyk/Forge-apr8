"""Tests for the factory health endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forge-factory"


@pytest.mark.anyio
async def test_root_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forge-factory"


@pytest.mark.anyio
async def test_ready_reports_dependency_success(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConnection:
        async def execute(self, _: object) -> None:
            return None

    class FakeConnectContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *_: object) -> None:
            return None

    class FakeEngine:
        def connect(self) -> FakeConnectContext:
            return FakeConnectContext()

    class FakeRedis:
        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("factory.api.health.get_engine", lambda: FakeEngine())
    monkeypatch.setattr("factory.api.health.aioredis.from_url", lambda *_args, **_kwargs: FakeRedis())

    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert {dependency["name"] for dependency in data["dependencies"]} == {"postgres", "redis"}


@pytest.mark.anyio
async def test_ready_reports_dependency_failure(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingEngine:
        def connect(self) -> object:
            raise RuntimeError("database offline")

    class FakeRedis:
        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("factory.api.health.get_engine", lambda: FailingEngine())
    monkeypatch.setattr("factory.api.health.aioredis.from_url", lambda *_args, **_kwargs: FakeRedis())

    response = await client.get("/api/v1/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert any(
        dependency["name"] == "postgres" and dependency["healthy"] is False and "database offline" in dependency["detail"]
        for dependency in data["dependencies"]
    )


@pytest.mark.anyio
async def test_recovery_reports_interrupted_builds(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBuild:
        id = "build-1"

    class FakeScalars:
        def all(self) -> list[FakeBuild]:
            return [FakeBuild()]

    class FakeResult:
        def scalars(self) -> FakeScalars:
            return FakeScalars()

    class FakeSession:
        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, _: Any) -> FakeResult:
            return FakeResult()

    class FakeSessionFactory:
        def __call__(self) -> FakeSession:
            return FakeSession()

    monkeypatch.setattr("factory.api.health.get_session_factory", lambda: FakeSessionFactory())

    response = await client.get("/api/v1/recovery")

    assert response.status_code == 200
    data = response.json()
    assert data["interrupted_builds"] == 1
    assert "build-1" in data["detail"]
