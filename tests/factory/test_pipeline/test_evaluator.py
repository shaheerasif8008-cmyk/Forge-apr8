"""Tests for the evaluator stage."""

from __future__ import annotations

import pytest

from factory.models.build import BuildStatus
from factory.pipeline.evaluator.test_runner import evaluate


@pytest.mark.anyio
async def test_evaluator_runs_black_box_suites(sample_build, monkeypatch) -> None:
    sample_build.metadata["image_tag"] = "forge:test"

    async def fake_start(image_tag, port):
        return "container-123"

    async def fake_stop(container_id):
        return None

    async def fake_wait(url, timeout=60):
        return True

    async def fake_suite(base_url):
        return {"passed": True, "tests": 1, "failures": []}

    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.find_free_port", lambda: 8123)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.start_container", fake_start)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.stop_container", fake_stop)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.wait_for_health", fake_wait)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_functional_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_security_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_behavioral_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_hallucination_tests", fake_suite)

    result = await evaluate(sample_build)
    assert result.status == BuildStatus.PASSED
    assert result.test_report["overall"] == "passed"
