from __future__ import annotations

from pathlib import Path

import pytest

from factory.models.build import Build
from factory.models.deployment import Deployment, DeploymentFormat, DeploymentStatus
from factory.pipeline.deployer.provisioner import provision


@pytest.mark.anyio
async def test_provisioner_dispatches_web_to_railway(sample_org, monkeypatch) -> None:
    deployment = Deployment(build_id=sample_org.id, org_id=sample_org.id, format=DeploymentFormat.WEB)
    build = Build(org_id=sample_org.id)
    build.metadata.update({"image_tarball": "/tmp/employee.tar", "employee_name": "Avery"})

    recorded: dict[str, object] = {}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    responses = iter(
        [
            FakeResponse(429, {}),
            FakeResponse(200, {"data": {"uploadImage": {"imageId": "img-1"}}}),
            FakeResponse(200, {"data": {"createService": {"serviceId": "svc-1", "domain": "avery.up.railway.app"}}}),
            FakeResponse(200, {"data": {"configureEnv": {"ok": True}}}),
            FakeResponse(200, {"data": {"deploymentStatus": {"state": "SUCCESS"}}}),
        ]
    )

    async def fake_post(self, url, json=None, headers=None):
        recorded.setdefault("calls", []).append({"url": url, "json": json, "headers": headers})
        return next(responses)

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("factory.pipeline.deployer.providers.railway.httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("factory.pipeline.deployer.providers.railway.asyncio.sleep", fake_sleep)

    result = await provision(deployment, build)

    assert result.infrastructure["provider"] == "railway"
    assert result.access_url == "https://avery.up.railway.app"
    assert len(recorded["calls"]) == 5


@pytest.mark.anyio
async def test_provisioner_dispatches_server_export(sample_org, tmp_path, monkeypatch) -> None:
    deployment = Deployment(build_id=sample_org.id, org_id=sample_org.id, format=DeploymentFormat.SERVER)
    build = Build(org_id=sample_org.id)
    build.metadata.update(
        {
            "build_dir": str(tmp_path),
            "runtime_template": "server_compose_bundle",
            "deployment_bundles": {
                "server": {
                    "artifact_path": str(tmp_path / "handoff.zip"),
                    "runtime_template": "server_compose_bundle",
                    "bundle_metadata_path": str(tmp_path / "bundle-metadata.json"),
                    "compose_file": "docker-compose.yml",
                    "healthcheck_path": "/api/v1/health",
                }
            },
        }
    )

    result = await provision(deployment, build)

    assert result.status == DeploymentStatus.PENDING_CLIENT_ACTION
    assert result.infrastructure["artifact_path"].endswith("handoff.zip")
    assert result.infrastructure["runtime_template"] == "server_compose_bundle"
    assert result.infrastructure["handoff_ready"] is True


@pytest.mark.anyio
async def test_provisioner_dispatches_local(sample_org, monkeypatch) -> None:
    deployment = Deployment(build_id=sample_org.id, org_id=sample_org.id, format=DeploymentFormat.LOCAL)
    build = Build(org_id=sample_org.id)
    build.metadata["image_tag"] = "forge:test"

    monkeypatch.setattr(
        "factory.pipeline.deployer.providers.local_docker.find_free_port",
        lambda: 8123,
    )

    async def fake_start_container(image_tag, port, *, name=None, environment="testing"):
        return "container-1"

    monkeypatch.setattr(
        "factory.pipeline.deployer.providers.local_docker.start_container",
        fake_start_container,
    )

    result = await provision(deployment, build)

    assert result.infrastructure["provider"] == "local_docker"
    assert result.access_url == "http://127.0.0.1:8123"
