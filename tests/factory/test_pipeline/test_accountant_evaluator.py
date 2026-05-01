from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.models.build import BuildStatus
from factory.pipeline.evaluator.accountant_tests import DATASET_PATH, load_accountant_cases, score_accountant_answer
from factory.pipeline.evaluator.test_runner import evaluate

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def test_accountant_dataset_contains_paid_fte_metadata_contract() -> None:
    raw_lines = [line for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = load_accountant_cases()

    assert len(cases) == len(raw_lines)
    assert len(cases) >= 8
    assert len(cases) <= 12
    for line in raw_lines:
        json.loads(line)
    for case in cases:
        assert case["lane"]
        assert case["workflow_stage"]
        assert isinstance(case["fixture_files"], list)
        assert case["fixture_files"]
        for fixture_file in case["fixture_files"]:
            assert (DATASET_PATH.parent.parent / fixture_file).exists(), fixture_file
        assert isinstance(case["required_evidence"], list)
        assert case["required_evidence"]
        assert 0.7 <= float(case["minimum_score"]) <= 1.0
        assert case["checks"]


def test_accountant_scoring_requires_evidence_terms_and_numeric_answers() -> None:
    case = {
        "id": "bank_reconciliation_sample",
        "minimum_score": 1.0,
        "required_evidence": ["bank statement", "GL cash detail", "outstanding checks"],
        "numeric_answers": [{"id": "adjusted_cash", "value": 10100.0, "tolerance": 0.01}],
        "checks": [{"id": "reconciliation", "all_of": ["adjusted cash", "unexplained difference", "escalate"]}],
    }

    weak_answer = "Adjusted cash is $10,100. There is an unexplained difference, so escalate."
    wrong_number_answer = (
        "Using the bank statement, GL cash detail, and outstanding checks, adjusted cash is $10,000. "
        "There is an unexplained difference, so escalate."
    )
    strong_answer = (
        "Using the bank statement, GL cash detail, and outstanding checks, adjusted cash is $10,100. "
        "There is an unexplained difference, so escalate."
    )

    weak_result = score_accountant_answer(weak_answer, case)
    wrong_number_result = score_accountant_answer(wrong_number_answer, case)
    strong_result = score_accountant_answer(strong_answer, case)

    assert weak_result["passed"] is False
    assert weak_result["evidence"][0]["passed"] is False
    assert wrong_number_result["passed"] is False
    assert wrong_number_result["numeric_answers"][0]["passed"] is False
    assert strong_result["passed"] is True
    assert strong_result["score"] == 1.0


def test_accountant_paid_proof_contract_doc_covers_launch_bar() -> None:
    contract = REPO_ROOT / "docs" / "proof" / "accountant_paid_proof_contract.md"
    text = contract.read_text(encoding="utf-8").lower()

    required_terms = [
        "$100k/year digital fte",
        "month-end close package",
        "bank",
        "gl",
        "ap",
        "ar",
        "reconciliation",
        "variance analysis",
        "statement draft",
        "escalation",
        "auditability",
        "sovereignty",
    ]
    for term in required_terms:
        assert term in text


@pytest.mark.anyio
async def test_evaluator_routes_accountant_builds_to_accountant_fixture_suite(sample_build, monkeypatch) -> None:
    sample_build.metadata.update(
        {
            "image_tag": "forge:test",
            "workflow_id": "accounting_ops",
            "evaluation_profile": "accounting_ops",
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
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_behavioral_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_hallucination_tests", fake_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_accountant_tests", fake_accountant_suite)
    monkeypatch.setattr("factory.pipeline.evaluator.test_runner.run_executive_assistant_tests", fake_suite)

    result = await evaluate(sample_build)

    assert result.status == BuildStatus.PASSED
    assert called.count("accountant") == 1
    assert result.test_report["suites"]["functional"]["tests"] == 3
