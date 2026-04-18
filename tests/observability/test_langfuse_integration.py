from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import component_library.data.context_assembler  # noqa: F401
import component_library.data.operational_memory  # noqa: F401
import component_library.data.org_context  # noqa: F401
import component_library.data.working_memory  # noqa: F401
import component_library.models.litellm_router  # noqa: F401
import component_library.quality.audit_system  # noqa: F401
import component_library.quality.confidence_scorer  # noqa: F401
import component_library.quality.input_protection  # noqa: F401
import component_library.quality.verification_layer  # noqa: F401
import component_library.tools.email_tool  # noqa: F401
import component_library.work.document_analyzer  # noqa: F401
import component_library.work.draft_generator  # noqa: F401
import component_library.work.text_processor  # noqa: F401
from component_library.component_factory import create_components
from component_library.models.anthropic_provider import AnthropicProvider
from component_library.models.litellm_router import LitellmRouter, TaskType
from employee_runtime.core.engine import EmployeeEngine
from factory.models.build import Build, BuildStatus
from factory.models.deployment import DeploymentStatus
from factory.observability.langfuse_client import (
    get_recorded_observations,
    reset_langfuse_client,
)
from factory.workers.pipeline_worker import start_pipeline
from tests.fixtures.sample_emails import CLEAR_QUALIFIED


def _completion_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return response


@pytest.mark.anyio
async def test_langfuse_disabled_is_noop() -> None:
    reset_langfuse_client(enabled=False)
    provider = AnthropicProvider()
    await provider.initialize({"model": "anthropic/claude-test"})
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=_completion_response("ok")):
        result = await provider.complete([{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert get_recorded_observations() == []


@pytest.mark.anyio
async def test_langfuse_records_model_generations_and_engine_spans() -> None:
    reset_langfuse_client(enabled=True)

    provider = AnthropicProvider()
    await provider.initialize({"model": "anthropic/claude-test"})
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=_completion_response("ok")):
        await provider.complete([{"role": "user", "content": "hi"}])

    router = LitellmRouter()
    await router.initialize(
        {
            "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
            "fallback_model": "openrouter/openai/gpt-4o",
        }
    )
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=_completion_response("done")):
        await router.complete([{"role": "user", "content": "hello"}], task_type=TaskType.DEFAULT)

    components = await create_components(
        [
            "litellm_router",
            "text_processor",
            "document_analyzer",
            "draft_generator",
            "operational_memory",
            "working_memory",
            "context_assembler",
            "org_context",
            "confidence_scorer",
            "audit_system",
            "input_protection",
            "verification_layer",
            "email_tool",
        ],
        {
            "litellm_router": {
                "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
                "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
            },
            "document_analyzer": {"practice_areas": ["personal injury", "employment", "commercial dispute"]},
            "draft_generator": {"default_attorney": "Arthur Review"},
            "operational_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "working_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "context_assembler": {"system_identity": "Arthur", "operational_memory": None},
            "org_context": {"people": [], "escalation_chain": []},
            "confidence_scorer": {},
            "audit_system": {},
            "input_protection": {},
            "verification_layer": {},
            "email_tool": {},
        },
    )
    components["context_assembler"]._operational_memory = components["operational_memory"]
    engine = EmployeeEngine("legal_intake", components, {"employee_id": "employee-1", "org_id": "org-1"})
    await engine.process_task(CLEAR_QUALIFIED)

    records = get_recorded_observations()
    assert any(record["kind"] == "generation" and record["name"] == "anthropic_provider.complete" for record in records)
    assert any(record["kind"] == "generation" and record["name"] == "litellm_router.complete" for record in records)
    assert any(record["kind"] == "trace" and record["name"] == "employee_workflow.legal_intake" for record in records)
    assert any(record["kind"] == "span" and record["name"].startswith("workflow.node.") for record in records)


@pytest.mark.anyio
async def test_langfuse_records_pipeline_spans(sample_requirements, sample_blueprint, monkeypatch) -> None:
    reset_langfuse_client(enabled=True)

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

    build = Build(requirements_id=sample_requirements.id, org_id=sample_requirements.org_id)
    await start_pipeline(sample_requirements, build)

    records = get_recorded_observations()
    assert any(record["kind"] == "trace" and record["name"] == "factory_pipeline" for record in records)
    assert any(record["kind"] == "span" and record["name"] == "pipeline.architect" for record in records)
    assert any(record["kind"] == "span" and record["name"] == "pipeline.packager" for record in records)
