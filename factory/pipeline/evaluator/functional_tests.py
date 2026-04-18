"""Functional evaluator test suite."""

from __future__ import annotations

from pathlib import Path

import httpx

from factory.pipeline.evaluator.deepeval_adapter import (
    answer_relevancy_metric,
    faithfulness_metric,
    json_schema_metric,
    load_cases,
)

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "legal_intake.jsonl"


async def run_functional_tests(base_url: str) -> dict[str, object]:
    """Submit representative intake tasks and score them with metric-style checks."""
    cases = load_cases(DATASET_PATH)
    failures: list[str] = []
    case_results: list[dict[str, object]] = []
    tests_run = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        for case in cases:
            response = await client.post(
                "/api/v1/tasks",
                json={"input": case["input"], "context": {"input_type": "email"}},
            )
            tests_run += 1
            if response.status_code != 200:
                failures.append(f"{case['id']}: task failed with status {response.status_code}")
                continue

            payload = response.json()
            metrics = [
                json_schema_metric(payload),
                answer_relevancy_metric(payload, case["expected_decision"]),
                faithfulness_metric(payload, case),
            ]
            tests_run += len(metrics)
            case_passed = all(metric.passed for metric in metrics)
            if not case_passed:
                failures.append(f"{case['id']}: one or more metrics failed")
            case_results.append(
                {
                    "id": case["id"],
                    "passed": case_passed,
                    "metrics": [metric.as_dict() for metric in metrics],
                }
            )

    return {
        "passed": len(failures) == 0,
        "tests": tests_run,
        "failures": failures,
        "cases": case_results,
    }
