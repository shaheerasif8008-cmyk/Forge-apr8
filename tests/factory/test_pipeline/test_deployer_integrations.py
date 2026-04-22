from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from factory.database import get_db_session
from factory.config import get_settings
from factory.main import app
from factory.models.build import Build, BuildStatus
from factory.models.deployment import Deployment, DeploymentStatus, IntegrationStatus
from factory.pipeline.deployer.activator import activate
from factory.pipeline.deployer.connector import Connector, pending_oauth_urls
from factory.workers.pipeline_worker import start_pipeline


class FakeComposioClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self._statuses: dict[str, str] = {}

    async def initiate_connection(self, *, deployment_id: str, tool_id: str, provider: str) -> dict[str, str]:
        connection_id = f"{deployment_id}-{tool_id}"
        self._statuses[connection_id] = "pending"
        return {
            "connection_id": connection_id,
            "oauth_url": f"https://oauth.example/{tool_id}",
        }

    async def get_connection_status(self, connection_id: str) -> str:
        return self._statuses.get(connection_id, "pending")

    async def delete_connection(self, connection_id: str) -> None:
        self.deleted.append(connection_id)


@pytest.mark.anyio
async def test_connector_and_activator_complete_successfully(sample_blueprint, sample_org, monkeypatch) -> None:
    fake_client = FakeComposioClient()
    deployment = Deployment(build_id=sample_org.id, org_id=sample_org.id)

    monkeypatch.setattr("factory.pipeline.deployer.connector.get_composio_client", lambda: fake_client)
    connector = Connector()
    deployment = await connector.connect(deployment, sample_blueprint)
    assert pending_oauth_urls(deployment)

    for integration in deployment.integrations:
        assert integration.composio_connection_id is not None
        fake_client._statuses[integration.composio_connection_id] = "connected"

    deployment.access_url = "http://127.0.0.1:9999"

    async def fake_wait_for_health(url, timeout=60):
        return True

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url):
            assert url == "http://127.0.0.1:9999/api/v1/runtime/recovery"
            return SimpleNamespace(status_code=200, json=lambda: {"startup_summary": {"interrupted_task_ids": []}})

    monkeypatch.setattr("factory.pipeline.deployer.activator.wait_for_health", fake_wait_for_health)
    monkeypatch.setattr("factory.pipeline.deployer.activator.httpx.AsyncClient", FakeAsyncClient)
    activated = await activate(deployment)

    assert activated.status == DeploymentStatus.ACTIVE
    assert all(integration.status == "connected" for integration in activated.integrations)
    assert activated.recovery_policy["health_endpoint"] == "/api/v1/health"
    assert activated.recovery_state["last_runtime_recovery"]["startup_summary"]["interrupted_task_ids"] == []


@pytest.mark.anyio
async def test_activator_times_out_waiting_for_client_action(sample_org, monkeypatch) -> None:
    deployment = Deployment(
        build_id=sample_org.id,
        org_id=sample_org.id,
        access_url="http://127.0.0.1:9999",
        integrations=[
            IntegrationStatus(
                tool_id="email_tool",
                provider="gmail",
                composio_connection_id="conn-1",
                oauth_url="https://oauth.example/email",
                status="pending",
            )
        ],
    )

    async def fake_wait_for_health(url, timeout=60):
        return True

    monkeypatch.setattr("factory.pipeline.deployer.activator.wait_for_health", fake_wait_for_health)

    class FakeLoop:
        def __init__(self) -> None:
            self._time = 0.0

        def time(self) -> float:
            self._time += 4000.0
            return self._time

    async def fake_sleep(_: float) -> None:
        return None

    async def fake_refresh(self, deployment):
        return deployment

    fake_loop = FakeLoop()
    monkeypatch.setattr("factory.pipeline.deployer.activator.asyncio.get_event_loop", lambda: fake_loop)
    monkeypatch.setattr("factory.pipeline.deployer.activator.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("factory.pipeline.deployer.activator.Connector.refresh_statuses", fake_refresh)

    activated = await activate(deployment)
    assert activated.status == DeploymentStatus.PENDING_CLIENT_ACTION


@pytest.mark.anyio
async def test_pipeline_rolls_back_on_activate_failure(sample_requirements, sample_blueprint, monkeypatch) -> None:
    calls: dict[str, int] = {"rollback": 0}

    @asynccontextmanager
    async def fake_session_factory():
        class FakeSession:
            async def commit(self) -> None:
                return None

        yield FakeSession()

    async def passthrough_requirements(session, requirements):
        return requirements

    async def passthrough_build(session, build):
        return build

    async def passthrough_blueprint(session, blueprint):
        return blueprint

    async def passthrough_deployment(session, deployment):
        return deployment

    async def fake_design(requirements):
        return sample_blueprint

    async def fake_assemble(blueprint, requirements, build):
        return build.model_copy(update={"metadata": {"build_dir": "/tmp/demo"}})

    async def fake_generate(blueprint, build, iteration=1):
        return build

    async def fake_package(build):
        return build.model_copy(update={"metadata": {"image_tag": "forge:test", **build.metadata}})

    async def fake_evaluate(build):
        return build.model_copy(update={"status": BuildStatus.PASSED})

    async def fake_provision(deployment, build):
        return deployment.model_copy(update={"access_url": "http://127.0.0.1:8123"})

    async def fake_connect(self, deployment, blueprint):
        deployment.integrations = [
            IntegrationStatus(
                tool_id="email_tool",
                provider="gmail",
                composio_connection_id="conn-1",
                oauth_url="https://oauth.example/email",
            )
        ]
        return deployment

    async def explode_activate(deployment):
        raise RuntimeError("activation failed")

    async def fake_rollback(deployment, session=None):
        calls["rollback"] += 1
        return deployment.model_copy(update={"status": DeploymentStatus.ROLLED_BACK, "access_url": "", "infrastructure": {}})

    monkeypatch.setattr(get_settings(), "human_review_required", False)
    monkeypatch.setattr("factory.workers.pipeline_worker._ensure_session_factory", lambda: fake_session_factory)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_requirements", passthrough_requirements)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_build", passthrough_build)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_blueprint", passthrough_blueprint)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_deployment", passthrough_deployment)
    monkeypatch.setattr("factory.pipeline.architect.designer.design_employee", fake_design)
    monkeypatch.setattr("factory.pipeline.builder.assembler.assemble", fake_assemble)
    monkeypatch.setattr("factory.pipeline.builder.generator.generate", fake_generate)
    monkeypatch.setattr("factory.pipeline.builder.packager.package", fake_package)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.evaluate", fake_evaluate)
    monkeypatch.setattr("factory.pipeline.deployer.provisioner.provision", fake_provision)
    monkeypatch.setattr("factory.pipeline.deployer.connector.Connector.connect", fake_connect)
    monkeypatch.setattr("factory.pipeline.deployer.activator.activate", explode_activate)
    monkeypatch.setattr("factory.pipeline.deployer.rollback.rollback", fake_rollback)

    build = Build(requirements_id=sample_requirements.id, org_id=sample_requirements.org_id)
    result = await start_pipeline(sample_requirements, build)

    assert calls["rollback"] == 1
    assert result.status == BuildStatus.FAILED


@pytest.mark.anyio
async def test_pipeline_marks_server_exports_pending_client_action(sample_requirements, sample_blueprint, monkeypatch) -> None:
    @asynccontextmanager
    async def fake_session_factory():
        class FakeSession:
            async def commit(self) -> None:
                return None

        yield FakeSession()

    server_requirements = sample_requirements.model_copy(update={"deployment_format": "server"})
    server_blueprint = sample_blueprint.model_copy(update={"org_id": server_requirements.org_id})

    async def passthrough_requirements(session, requirements):
        return requirements

    async def passthrough_build(session, build):
        return build

    async def passthrough_blueprint(session, blueprint):
        return blueprint

    async def passthrough_deployment(session, deployment):
        return deployment

    async def fake_design(requirements):
        return server_blueprint

    async def fake_assemble(blueprint, requirements, build):
        return build.model_copy(update={"metadata": {"build_dir": "/tmp/demo"}})

    async def fake_generate(blueprint, build, iteration=1):
        return build

    async def fake_package(build):
        return build.model_copy(update={"metadata": {"image_tag": "forge:test", **build.metadata}})

    async def fake_evaluate(build):
        return build.model_copy(update={"status": BuildStatus.PASSED})

    async def fake_provision(deployment, build):
        return deployment.model_copy(update={"status": DeploymentStatus.PENDING_CLIENT_ACTION, "access_url": ""})

    async def fake_activate(deployment):
        raise AssertionError("activate should not run for pending client action deployments")

    monkeypatch.setattr(get_settings(), "human_review_required", False)
    monkeypatch.setattr("factory.workers.pipeline_worker._ensure_session_factory", lambda: fake_session_factory)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_requirements", passthrough_requirements)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_build", passthrough_build)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_blueprint", passthrough_blueprint)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_deployment", passthrough_deployment)
    monkeypatch.setattr("factory.pipeline.architect.designer.design_employee", fake_design)
    monkeypatch.setattr("factory.pipeline.builder.assembler.assemble", fake_assemble)
    monkeypatch.setattr("factory.pipeline.builder.generator.generate", fake_generate)
    monkeypatch.setattr("factory.pipeline.builder.packager.package", fake_package)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.evaluate", fake_evaluate)
    monkeypatch.setattr("factory.pipeline.deployer.provisioner.provision", fake_provision)
    monkeypatch.setattr("factory.pipeline.deployer.activator.activate", fake_activate)

    build = Build(requirements_id=server_requirements.id, org_id=server_requirements.org_id)
    result = await start_pipeline(server_requirements, build)

    assert result.status == BuildStatus.PENDING_CLIENT_ACTION


@pytest.mark.anyio
async def test_deployment_api_exposes_pending_urls_and_accepts_callback(client, sample_org, monkeypatch) -> None:
    deployment = Deployment(
        build_id=sample_org.id,
        org_id=sample_org.id,
        integrations=[
            IntegrationStatus(
                tool_id="email_tool",
                provider="gmail",
                composio_connection_id="conn-1",
                oauth_url="https://oauth.example/email",
                status="pending",
            )
        ],
    )

    async def fake_db():
        yield object()

    async def fake_get_deployment(session, deployment_id):
        return deployment

    async def fake_save_deployment(session, deployment_to_save):
        return deployment_to_save

    async def fake_handle_callback(self, deployment_to_update, **kwargs):
        deployment_to_update.integrations[0].status = "connected"
        deployment_to_update.integrations[0].composio_connection_id = kwargs.get("connection_id")
        return deployment_to_update

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.deployments.get_deployment", fake_get_deployment)
    monkeypatch.setattr("factory.api.deployments.save_deployment", fake_save_deployment)
    monkeypatch.setattr("factory.api.deployments.Connector.handle_callback", fake_handle_callback)

    urls_response = await client.get(f"/api/v1/deployments/{deployment.id}/integrations/urls")
    callback_response = await client.post(
        f"/api/v1/deployments/{deployment.id}/integrations/callback",
        json={
            "tool_id": "email_tool",
            "provider": "gmail",
            "composio_connection_id": "conn-updated",
            "status": "connected",
        },
    )
    app.dependency_overrides.clear()

    assert urls_response.status_code == 200
    assert urls_response.json() == [{"tool_id": "email_tool", "oauth_url": "https://oauth.example/email"}]
    assert callback_response.status_code == 200
    assert callback_response.json()["integrations"][0]["status"] == "connected"
