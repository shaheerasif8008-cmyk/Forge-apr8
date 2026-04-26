"""Test runner: orchestrates evaluator test suites against a packaged employee."""

from __future__ import annotations

import structlog
from collections.abc import Awaitable, Callable
from typing import Any

from factory.models.build import Build, BuildLog, BuildStatus
from factory.pipeline.evaluator.behavioral_tests import run_behavioral_tests
from factory.pipeline.evaluator.container_runner import (
    find_free_port,
    start_container,
    stop_container,
    wait_for_health,
)
from factory.pipeline.evaluator.executive_assistant_tests import run_executive_assistant_tests
from factory.pipeline.evaluator.functional_tests import run_functional_tests
from factory.pipeline.evaluator.hallucination_tests import run_hallucination_tests
from factory.pipeline.evaluator.security_tests import run_security_tests

logger = structlog.get_logger(__name__)


def _suite_profile(build: Build) -> str:
    return str(build.metadata.get("workflow_id", "legal_intake"))


async def evaluate(build: Build) -> Build:
    """Run evaluator suites against the packaged employee container."""
    build.status = BuildStatus.EVALUATING
    image_tag = str(build.metadata.get("image_tag", ""))
    if not image_tag:
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(stage="evaluator", level="error", message="Missing image tag for evaluation")
        )
        return build

    port = find_free_port()
    container_id = ""
    base_url = f"http://127.0.0.1:{port}"

    logger.info("evaluator_start", build_id=str(build.id), image_tag=image_tag, port=port)
    try:
        container_id = await start_container(image_tag, port)
        build.metadata["evaluator_container_id"] = container_id
        build.metadata["evaluator_port"] = port

        healthy = await wait_for_health(f"{base_url}/health", timeout=60)
        if not healthy:
            build.status = BuildStatus.FAILED
            build.logs.append(
                BuildLog(stage="evaluator", level="error", message="Employee failed health check")
            )
            return build

        api_token = str(build.metadata.get("employee_api_token", "")).strip()
        auth_headers = {"Authorization": f"Bearer {api_token}"} if api_token else None
        workflow_id = _suite_profile(build)
        suites = {
            "security": await _run_suite(run_security_tests, base_url, auth_headers),
            "behavioral": await _run_suite(run_behavioral_tests, base_url, auth_headers),
            "hallucination": await _run_suite(run_hallucination_tests, base_url, auth_headers),
        }
        if workflow_id == "executive_assistant":
            suites["functional"] = await _run_suite(run_executive_assistant_tests, base_url, auth_headers)
        else:
            suites["functional"] = await _run_suite(run_functional_tests, base_url, auth_headers)
        for suite_name, result in suites.items():
            build.logs.append(
                BuildLog(
                    stage="evaluator",
                    message=f"Suite {suite_name}: {'passed' if result['passed'] else 'failed'}",
                    detail=result,
                )
            )
        passed = all(result["passed"] for result in suites.values())
        build.test_report = {"suites": suites, "overall": "passed" if passed else "failed"}
        build.status = BuildStatus.PASSED if passed else BuildStatus.FAILED
        logger.info("evaluator_complete", build_id=str(build.id), overall=build.test_report["overall"])
        return build
    finally:
        if container_id:
            await stop_container(container_id)
            build.metadata.pop("evaluator_container_id", None)
            build.metadata.pop("evaluator_port", None)


async def _run_suite(
    suite: Callable[..., Awaitable[dict[str, Any]]],
    base_url: str,
    auth_headers: dict[str, str] | None,
) -> dict[str, Any]:
    try:
        return await suite(base_url, auth_headers=auth_headers)
    except TypeError as exc:
        if "auth_headers" not in str(exc):
            raise
        return await suite(base_url)
