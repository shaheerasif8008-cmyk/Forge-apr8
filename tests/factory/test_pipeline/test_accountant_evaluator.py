from __future__ import annotations

import pytest

from factory.models.build import BuildStatus
from factory.pipeline.evaluator.accountant_tests import score_accountant_answer
from factory.pipeline.evaluator.test_runner import evaluate


def test_accountant_scoring_uses_structured_case_expectations() -> None:
    answer = """
    ASC 606 / IFRS 15 steps: identify the contract, identify performance obligations,
    determine the transaction price, allocate the transaction price, and recognize revenue.
    Weighted-average inventory COGS is $3,666.67 and ending inventory is $1,833.33.
    The lease is an operating lease. A $1,000 deduction saves $210 while a $1,000 credit saves $1,000.
    Taxable income is $455,000. Wayfair and physical presence both matter for nexus.
    Performance materiality differs from overall materiality. =XLOOKUP(A2,A:A,D:D,"Not found").
    The bank reconciliation has a $10,100 adjusted bank balance and an unexplained difference.
    Use a self join within 24 hours. Integrity requires refusal and escalation. ASC 350-40 and securities fraud risk apply.
    """

    result = score_accountant_answer(
        answer,
        {
            "id": "sample",
            "checks": [
                {"id": "asc606", "all_of": ["identify the contract", "performance obligations", "recognize revenue"]},
                {"id": "inventory", "any_of": ["$3,666.67", "3666.67"]},
                {"id": "ethics", "all_of": ["integrity", "refusal"]},
            ],
            "minimum_score": 1.0,
        },
    )

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert [check["id"] for check in result["checks"]] == ["asc606", "inventory", "ethics"]


@pytest.mark.anyio
async def test_evaluator_routes_accountant_builds_to_accountant_fixture_suite(sample_build, monkeypatch) -> None:
    sample_build.metadata.update(
        {
            "image_tag": "forge:test",
            "workflow_id": "executive_assistant",
            "employee_role": "AI Accountant",
        }
    )
    called: list[str] = []

    async def fake_start(image_tag, port):
        return "container-123"

    async def fake_stop(container_id):
        return None

    async def fake_wait(url, timeout=60):
        return True

    async def fake_suite(base_url, *, auth_headers=None):
        called.append("generic")
        return {"passed": True, "tests": 1, "failures": []}

    async def fake_accountant_suite(base_url, *, auth_headers=None):
        called.append("accountant")
        return {"passed": True, "tests": 3, "failures": [], "cases": []}

    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.find_free_port", lambda: 8123)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.start_container", fake_start)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.stop_container", fake_stop)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.wait_for_health", fake_wait)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_security_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_baseline_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_behavioral_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_hallucination_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_accountant_tests", fake_accountant_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_executive_assistant_tests", fake_suite)

    result = await evaluate(sample_build)

    assert result.status == BuildStatus.PASSED
    assert called.count("accountant") == 1
    assert result.test_report["suites"]["functional"]["tests"] == 3
