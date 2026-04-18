from __future__ import annotations

import json
import subprocess

import pytest

from factory.config import get_settings
from factory.models.blueprint import CustomCodeSpec
from factory.models.build import BuildStatus
from factory.pipeline.builder.generator import ModelCallResult, _call_model, generate


def _module_response(name: str) -> ModelCallResult:
    return ModelCallResult(
        content=(
            "```python\n"
            "from __future__ import annotations\n\n"
            "from typing import Any\n\n"
            "from component_library.interfaces import BaseComponent, ComponentHealth\n"
            "from component_library.registry import register\n\n"
            f"@register({name!r})\n"
            "class GeneratedComponent(BaseComponent):\n"
            f"    component_id = {name!r}\n"
            "    version = '1.0.0'\n"
            "    category = 'work'\n\n"
            "    async def initialize(self, config: dict[str, Any]) -> None:\n"
            "        self.config = config\n\n"
            "    async def health_check(self) -> ComponentHealth:\n"
            "        return ComponentHealth(healthy=True, detail='ok')\n\n"
            "    def get_test_suite(self) -> list[str]:\n"
            "        return []\n"
            "```\n"
        ),
        cost_usd=0.12,
        model="test-model",
    )


def _test_response(name: str) -> ModelCallResult:
    return ModelCallResult(
        content=(
            "```python\n"
            f"from generated.{name} import GeneratedComponent\n\n"
            "def test_generated_component_smoke() -> None:\n"
            "    assert GeneratedComponent.component_id\n"
            "```\n"
        ),
        cost_usd=0.05,
        model="test-model",
    )


@pytest.mark.anyio
async def test_generator_retries_until_generated_tests_pass(
    sample_blueprint,
    sample_build,
    monkeypatch,
    tmp_path,
) -> None:
    sample_blueprint.custom_code_specs = [
        CustomCodeSpec(name="custom_case_router", description="Route edge cases", inputs={"text": "str"}, outputs={"route": "str"})
    ]
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "package_manifest.json"
    config_path = tmp_path / "config.yaml"
    manifest_path.write_text(json.dumps({"artifact_manifest": {}}, indent=2))
    config_path.write_text(json.dumps({"manifest": {"artifact_manifest": {}}}, indent=2))
    sample_build.metadata.update(
        {
            "generated_dir": str(generated_dir),
            "manifest_path": str(manifest_path),
            "config_path": str(config_path),
        }
    )

    responses = iter(
        [
            _module_response("custom_case_router"),
            _test_response("custom_case_router"),
            _module_response("custom_case_router"),
        ]
    )
    test_results = iter(
        [
            subprocess.CompletedProcess(args=["pytest"], returncode=1, stdout="", stderr="failed"),
            subprocess.CompletedProcess(args=["pytest"], returncode=0, stdout="passed", stderr=""),
        ]
    )

    async def fake_create_client(settings):
        return object()

    async def fake_call_model(client, prompt, model):
        return next(responses)

    def fake_run_generated_tests(*, test_path, build_dir, timeout):
        return next(test_results)

    monkeypatch.setattr("factory.pipeline.builder.generator._create_generation_client", fake_create_client)
    monkeypatch.setattr("factory.pipeline.builder.generator._call_model", fake_call_model)
    monkeypatch.setattr("factory.pipeline.builder.generator._run_generated_tests", fake_run_generated_tests)

    result = await generate(sample_blueprint, sample_build)

    assert result.status == BuildStatus.GENERATING
    assert result.metadata["generation_cost_usd"] == pytest.approx(0.29)
    assert any(log.stage == "generator" for log in result.logs)
    assert (generated_dir / "custom_case_router.py").exists()
    assert (generated_dir / "test_custom_case_router.py").exists()


@pytest.mark.anyio
async def test_generator_fails_after_max_iterations(
    sample_blueprint,
    sample_build,
    monkeypatch,
    tmp_path,
) -> None:
    settings = get_settings()
    sample_blueprint.custom_code_specs = [
        CustomCodeSpec(name="custom_policy_gate", description="Policy gate", inputs={}, outputs={})
    ]
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "package_manifest.json"
    config_path = tmp_path / "config.yaml"
    manifest_path.write_text(json.dumps({"artifact_manifest": {}}, indent=2))
    config_path.write_text(json.dumps({"manifest": {"artifact_manifest": {}}}, indent=2))
    sample_build.metadata.update(
        {
            "generated_dir": str(generated_dir),
            "manifest_path": str(manifest_path),
            "config_path": str(config_path),
        }
    )

    responses = [_module_response("custom_policy_gate"), _test_response("custom_policy_gate")]
    responses.extend(_module_response("custom_policy_gate") for _ in range(settings.max_generation_iterations - 1))
    response_iter = iter(responses)

    async def fake_create_client(settings):
        return object()

    async def fake_call_model(client, prompt, model):
        return next(response_iter)

    def fake_run_generated_tests(*, test_path, build_dir, timeout):
        return subprocess.CompletedProcess(args=["pytest"], returncode=1, stdout="", stderr="still failing")

    monkeypatch.setattr("factory.pipeline.builder.generator._create_generation_client", fake_create_client)
    monkeypatch.setattr("factory.pipeline.builder.generator._call_model", fake_call_model)
    monkeypatch.setattr("factory.pipeline.builder.generator._run_generated_tests", fake_run_generated_tests)

    result = await generate(sample_blueprint, sample_build)

    assert result.status == BuildStatus.FAILED
    assert "generation_cost_usd" in result.metadata
    assert any(log.level == "error" for log in result.logs)


@pytest.mark.anyio
async def test_cost_math_uses_real_usage_counts(
    sample_blueprint,
    sample_build,
    monkeypatch,
    tmp_path,
) -> None:
    sample_blueprint.custom_code_specs = [
        CustomCodeSpec(name="custom_cost_gate", description="Track costs", inputs={}, outputs={})
    ]
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "package_manifest.json"
    config_path = tmp_path / "config.yaml"
    manifest_path.write_text(json.dumps({"artifact_manifest": {}}, indent=2))
    config_path.write_text(json.dumps({"manifest": {"artifact_manifest": {}}}, indent=2))
    sample_build.metadata.update(
        {
            "generated_dir": str(generated_dir),
            "manifest_path": str(manifest_path),
            "config_path": str(config_path),
        }
    )

    class _FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete_with_usage(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _module_response("custom_cost_gate").content, {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                }
            return _test_response("custom_cost_gate").content, {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
            }

    async def fake_create_client(settings):
        return _FakeClient()

    def fake_run_generated_tests(*, test_path, build_dir, timeout):
        return subprocess.CompletedProcess(args=["pytest"], returncode=0, stdout="passed", stderr="")

    monkeypatch.setattr("factory.pipeline.builder.generator._create_generation_client", fake_create_client)
    monkeypatch.setattr("factory.pipeline.builder.generator._run_generated_tests", fake_run_generated_tests)

    result = await generate(sample_blueprint, sample_build)

    assert result.status == BuildStatus.GENERATING
    assert result.metadata["generation_cost_usd"] == pytest.approx(0.00126)


@pytest.mark.anyio
async def test_call_model_uses_complete_with_usage() -> None:
    class _FakeClient:
        async def complete_with_usage(self, *args, **kwargs):
            return "ok", {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}

    result = await _call_model(_FakeClient(), "prompt", "anthropic/claude-3-5-sonnet-20241022")

    assert result.content == "ok"
    assert result.cost_usd == pytest.approx(0.00009)
