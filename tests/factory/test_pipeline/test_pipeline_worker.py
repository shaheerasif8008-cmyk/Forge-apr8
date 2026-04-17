"""Integration test for the full factory pipeline (no Docker required)."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from factory.models.build import Build, BuildStatus
from factory.models.deployment import DeploymentStatus
from factory.workers.pipeline_worker import start_pipeline


@pytest.mark.anyio
async def test_pipeline_completes(sample_requirements, sample_blueprint, monkeypatch) -> None:
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
        return build

    async def fake_generate(blueprint, build, iteration=1):
        return build

    async def fake_package(build):
        return build.model_copy(update={"metadata": {"image_tag": "forge:test"}})

    async def fake_evaluate(build):
        return build.model_copy(update={"status": BuildStatus.PASSED})

    async def fake_correction(blueprint, build):
        return build

    async def fake_provision(deployment, build):
        return deployment.model_copy(update={"access_url": "http://127.0.0.1:9001"})

    async def fake_activate(deployment):
        return deployment.model_copy(update={"status": DeploymentStatus.ACTIVE})

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
    monkeypatch.setattr("factory.pipeline.evaluator.self_correction.correction_loop", fake_correction)
    monkeypatch.setattr("factory.pipeline.deployer.provisioner.provision", fake_provision)
    monkeypatch.setattr("factory.pipeline.deployer.activator.activate", fake_activate)

    build = Build(
        requirements_id=sample_requirements.id,
        org_id=sample_requirements.org_id,
    )
    result = await start_pipeline(sample_requirements, build)
    assert result.status == BuildStatus.DEPLOYED


@pytest.mark.anyio
async def test_pipeline_stops_after_generation_failure(sample_requirements, sample_blueprint, monkeypatch) -> None:
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

    async def fake_design(requirements):
        return sample_blueprint

    async def fake_assemble(blueprint, requirements, build):
        return build

    async def fake_generate(blueprint, build, iteration=1):
        return build.model_copy(update={"status": BuildStatus.FAILED})

    async def fake_package(build):
        raise AssertionError("packager should not run after generation failure")

    monkeypatch.setattr("factory.workers.pipeline_worker._ensure_session_factory", lambda: fake_session_factory)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_requirements", passthrough_requirements)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_build", passthrough_build)
    monkeypatch.setattr("factory.workers.pipeline_worker.save_blueprint", passthrough_blueprint)
    monkeypatch.setattr("factory.pipeline.architect.designer.design_employee", fake_design)
    monkeypatch.setattr("factory.pipeline.builder.assembler.assemble", fake_assemble)
    monkeypatch.setattr("factory.pipeline.builder.generator.generate", fake_generate)
    monkeypatch.setattr("factory.pipeline.builder.packager.package", fake_package)

    build = Build(requirements_id=sample_requirements.id, org_id=sample_requirements.org_id)
    result = await start_pipeline(sample_requirements, build)

    assert result.status == BuildStatus.FAILED
