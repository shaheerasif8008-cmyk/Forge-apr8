"""Hallucination evaluator suite."""

from __future__ import annotations

from pathlib import Path

import httpx

from factory.pipeline.evaluator.deepeval_adapter import hallucination_metric, load_cases

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "legal_intake.jsonl"


async def run_hallucination_tests(base_url: str) -> dict[str, object]:
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
            metric = hallucination_metric(response.json(), case["input"])
            tests_run += 1
            case_results.append({"id": case["id"], "metric": metric.as_dict()})
            if not metric.passed:
                failures.append(f"{case['id']}: hallucination score too high")

    return {
        "passed": len(failures) == 0,
        "tests": tests_run,
        "failures": failures,
        "cases": case_results,
    }
