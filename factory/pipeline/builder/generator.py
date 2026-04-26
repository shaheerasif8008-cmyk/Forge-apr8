"""Generator: writes custom code for capabilities not covered by the library (≈20%)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from component_library.models.litellm_router import LitellmRouter, TaskType
from factory.config import FactorySettings, get_settings
from factory.models.blueprint import EmployeeBlueprint
from factory.models.build import Build, BuildLog, BuildStatus

logger = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
REPO_ROOT = Path(__file__).resolve().parents[3]
MAX_LOG_TEXT = 4000
MODEL_COST_PER_TOKEN_USD = {
    "anthropic/claude-3-5-sonnet-20241022": {"input": 0.000003, "output": 0.000015},
    "anthropic/claude-3-5-haiku-20241022": {"input": 0.0000008, "output": 0.000004},
    "openrouter/anthropic/claude-3.5-sonnet": {"input": 0.000003, "output": 0.000015},
    "openrouter/openai/gpt-4o": {"input": 0.0000025, "output": 0.00001},
}
DEFAULT_MODEL_RATE = MODEL_COST_PER_TOKEN_USD["anthropic/claude-3-5-sonnet-20241022"]


@dataclass(slots=True)
class ModelCallResult:
    content: str
    cost_usd: float
    model: str


async def generate(blueprint: EmployeeBlueprint, build: Build, iteration: int = 1) -> Build:
    """Generate custom code for each CustomCodeSpec in the blueprint."""
    build.status = BuildStatus.GENERATING
    build.iteration = iteration
    logger.info(
        "generator_start",
        build_id=str(build.id),
        spec_count=len(blueprint.custom_code_specs),
        iteration=iteration,
    )

    generated_dir = Path(str(build.metadata.get("generated_dir", "")))
    if blueprint.custom_code_specs and not generated_dir.exists():
        generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "__init__.py").write_text("")

    if not blueprint.custom_code_specs:
        build.logs.append(BuildLog(stage="generator", message="No custom code specs requested"))
        return build

    settings = get_settings()
    client_result = await _create_generation_client(settings)
    if isinstance(client_result, tuple):
        client, generation_model = client_result
    else:
        client = client_result
        generation_model = _resolve_generation_model(settings)
    generated_files: list[str] = []
    total_generation_cost = float(build.metadata.get("generation_cost_usd", 0.0))

    for spec in blueprint.custom_code_specs:
        module_path = generated_dir / f"{spec.name}.py"
        test_path = generated_dir / f"test_{spec.name}.py"

        module_prompt = _render_prompt(
            "custom_module_template.md",
            spec_name=spec.name,
            spec_description=spec.description,
            spec_inputs=json.dumps(spec.inputs, indent=2, sort_keys=True),
            spec_outputs=json.dumps(spec.outputs, indent=2, sort_keys=True),
            workflow_id=blueprint.workflow_id,
            interface_source=(REPO_ROOT / "component_library" / "interfaces.py").read_text(),
            existing_component_example=(REPO_ROOT / "component_library" / "work" / "text_processor.py").read_text(),
        )
        module_result = await _call_model(client, module_prompt, generation_model)
        total_generation_cost += module_result.cost_usd
        module_code = _extract_code_block(module_result.content)
        validation_attempt = 1
        while True:
            try:
                _validate_generated_module(module_code)
                break
            except ValueError as exc:
                if validation_attempt >= settings.max_generation_iterations:
                    build.status = BuildStatus.FAILED
                    build.logs.append(
                        BuildLog(
                            stage="generator",
                            level="error",
                            message=f"Generated module contract validation failed for {spec.name}",
                            detail={
                                "iteration_number": validation_attempt,
                                "validation_error": str(exc),
                                "response": module_result.content[-MAX_LOG_TEXT:],
                            },
                        )
                    )
                    build.metadata["generation_cost_usd"] = round(total_generation_cost, 6)
                    build.metadata["generated_files"] = generated_files
                    _sync_generated_files(build)
                    return build
                validation_attempt += 1
                fix_prompt = _build_fix_prompt(
                    spec_name=spec.name,
                    current_code=module_code,
                    current_test="",
                    pytest_output=f"Contract validation failed: {exc}",
                )
                module_result = await _call_model(client, fix_prompt, generation_model)
                total_generation_cost += module_result.cost_usd
                module_code = _extract_code_block(module_result.content)
        module_path.write_text(module_code)

        test_prompt = _render_prompt(
            "test_generation_template.md",
            spec_name=spec.name,
            spec_description=spec.description,
            module_import_path=f"generated.{spec.name}",
            workflow_id=blueprint.workflow_id,
            spec_inputs=json.dumps(spec.inputs, indent=2, sort_keys=True),
            spec_outputs=json.dumps(spec.outputs, indent=2, sort_keys=True),
        )
        test_result = await _call_model(client, test_prompt, generation_model)
        total_generation_cost += test_result.cost_usd
        test_code = _extract_code_block(test_result.content)
        test_path.write_text(test_code)

        generated_files.extend([str(module_path), str(test_path)])
        pytest_result = _run_generated_tests(
            test_path=test_path,
            build_dir=generated_dir.parent,
            timeout=settings.generator_test_timeout,
        )
        _append_generation_log(
            build,
            spec_name=spec.name,
            iteration_number=1,
            prompt=module_prompt,
            response=module_result.content,
            test_result=_format_test_result(pytest_result),
        )
        _append_generation_log(
            build,
            spec_name=f"{spec.name}_tests",
            iteration_number=1,
            prompt=test_prompt,
            response=test_result.content,
            test_result=_format_test_result(pytest_result),
        )

        iteration_number = 1
        while pytest_result.returncode != 0 and iteration_number < settings.max_generation_iterations:
            iteration_number += 1
            fix_prompt = _build_fix_prompt(
                spec_name=spec.name,
                current_code=module_path.read_text(),
                current_test=test_path.read_text(),
                pytest_output=_format_test_result(pytest_result),
            )
            fixed_result = await _call_model(client, fix_prompt, generation_model)
            total_generation_cost += fixed_result.cost_usd
            fixed_code = _extract_code_block(fixed_result.content)
            _validate_generated_module(fixed_code)
            module_path.write_text(fixed_code)
            pytest_result = _run_generated_tests(
                test_path=test_path,
                build_dir=generated_dir.parent,
                timeout=settings.generator_test_timeout,
            )
            _append_generation_log(
                build,
                spec_name=spec.name,
                iteration_number=iteration_number,
                prompt=fix_prompt,
                response=fixed_result.content,
                test_result=_format_test_result(pytest_result),
            )

        if pytest_result.returncode != 0:
            build.status = BuildStatus.FAILED
            build.logs.append(
                BuildLog(
                    stage="generator",
                    level="error",
                    message=f"Generated tests never passed for {spec.name}",
                    detail={
                        "iteration_number": iteration_number,
                        "file_path": str(module_path),
                        "test_path": str(test_path),
                        "pytest_output": _format_test_result(pytest_result)[-MAX_LOG_TEXT:],
                    },
                )
            )
            build.metadata["generation_cost_usd"] = round(total_generation_cost, 6)
            build.metadata["generated_files"] = generated_files
            _sync_generated_files(build)
            return build

    build.metadata["generated_files"] = generated_files
    build.metadata["generation_cost_usd"] = round(total_generation_cost, 6)
    _sync_generated_files(build)
    return build


def _resolve_generation_model(settings: FactorySettings) -> str:
    if settings.anthropic_api_key:
        return settings.generator_model
    if settings.openai_api_key:
        return "gpt-4o"
    if settings.openrouter_api_key:
        return settings.llm_primary_model
    return settings.generator_model


async def _create_generation_client(settings: FactorySettings) -> tuple[LitellmRouter, str]:
    model = _resolve_generation_model(settings)
    client = LitellmRouter()
    await client.initialize(
        {
            "primary_model": model,
            "fallback_model": settings.llm_fallback_model,
            "max_tokens": 4096,
            "timeout": max(settings.generator_test_timeout, 60),
        }
    )
    return client, model


async def _call_model(
    client: LitellmRouter,
    prompt: str,
    model: str,
) -> ModelCallResult:
    messages = [{"role": "user", "content": prompt}]
    system = (
        "You are Forge's Builder. Return exactly what the prompt requests. "
        f"Use the configured model {model}."
    )
    complete_with_usage = getattr(client, "complete_with_usage", None)
    if callable(complete_with_usage):
        content, usage = await complete_with_usage(
            messages,
            max_tokens=4096,
            temperature=0.2,
            task_type=TaskType.CREATIVE,
            system=system,
        )
        return ModelCallResult(
            content=str(content),
            cost_usd=_usage_cost_usd(model, usage),
            model=model,
        )

    content = await client.complete(
        messages,
        max_tokens=4096,
        temperature=0.2,
        task_type=TaskType.CREATIVE,
        system=system,
    )
    return ModelCallResult(content=content, cost_usd=0.0, model=model)


def _usage_cost_usd(model: str, usage: dict[str, object]) -> float:
    rates = _model_cost_for(model)
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return (prompt_tokens * rates["input"]) + (completion_tokens * rates["output"])


def _model_cost_for(model: str) -> dict[str, float]:
    rates = MODEL_COST_PER_TOKEN_USD.get(model)
    if rates is not None:
        return rates
    logger.warning("generator_unknown_model_cost", model=model, fallback_model="anthropic/claude-3-5-sonnet-20241022")
    return DEFAULT_MODEL_RATE


def _render_prompt(template_name: str, **values: str) -> str:
    rendered = (PROMPTS_DIR / template_name).read_text()
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _extract_code_block(content: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    return content.strip() + "\n"


def _validate_generated_module(code: str) -> None:
    if "@register(" not in code or "BaseComponent" not in code:
        raise ValueError("Generated code does not satisfy BaseComponent registration requirements.")


def _run_generated_tests(
    *,
    test_path: Path,
    build_dir: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{build_dir}:{existing_pythonpath}" if existing_pythonpath else str(build_dir)
    )
    return subprocess.run(
        ["pytest", str(test_path), "-x", "-q"],
        cwd=str(build_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _build_fix_prompt(
    *,
    spec_name: str,
    current_code: str,
    current_test: str,
    pytest_output: str,
) -> str:
    return (
        f"Fix the generated Forge component `{spec_name}`.\n\n"
        "Return ONLY Python code in a single ```python``` block.\n\n"
        f"Current module:\n```python\n{current_code}\n```\n\n"
        f"Current test:\n```python\n{current_test}\n```\n\n"
        f"Pytest output:\n```\n{pytest_output[-MAX_LOG_TEXT:]}\n```\n"
    )


def _append_generation_log(
    build: Build,
    *,
    spec_name: str,
    iteration_number: int,
    prompt: str,
    response: str,
    test_result: str,
) -> None:
    build.logs.append(
        BuildLog(
            stage="generator",
            message=f"Generated artifact iteration for {spec_name}",
            detail={
                "spec_name": spec_name,
                "iteration_number": iteration_number,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "response_length": len(response),
                "test_result": test_result[-MAX_LOG_TEXT:],
                "prompt_preview": prompt[-MAX_LOG_TEXT:],
                "response_preview": response[-MAX_LOG_TEXT:],
            },
        )
    )


def _format_test_result(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def _sync_generated_files(build: Build) -> None:
    generated_files = list(build.metadata.get("generated_files", []))
    manifest_path = Path(str(build.metadata.get("manifest_path", "")))
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest.setdefault("artifact_manifest", {})
        manifest["artifact_manifest"]["generated_files"] = generated_files
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    config_path = Path(str(build.metadata.get("config_path", "")))
    if config_path.exists():
        config = json.loads(config_path.read_text())
        manifest = config.setdefault("manifest", {})
        artifact_manifest = manifest.setdefault("artifact_manifest", {})
        artifact_manifest["generated_files"] = generated_files
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True))
