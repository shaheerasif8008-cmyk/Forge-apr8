"""Evaluator suite for accountant employees."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "accountant_tasks.jsonl"
EVALUATOR_REQUEST_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_REQUEST_TIMEOUT_SECONDS", "300"))


def load_accountant_cases(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_accountant_answer(answer: str, case: dict[str, Any]) -> dict[str, Any]:
    normalized = " ".join(answer.lower().replace(",", "").split())
    checks: list[dict[str, Any]] = []
    passed_count = 0
    for check in case.get("checks", []):
        all_of = [str(term).lower().replace(",", "") for term in check.get("all_of", [])]
        any_of = [str(term).lower().replace(",", "") for term in check.get("any_of", [])]
        missing_all = [term for term in all_of if term not in normalized]
        any_matched = True if not any_of else any(term in normalized for term in any_of)
        passed = not missing_all and any_matched
        if passed:
            passed_count += 1
        checks.append(
            {
                "id": check.get("id", ""),
                "passed": passed,
                "missing_all": missing_all,
                "matched_any": any_matched,
            }
        )
    total = len(checks)
    score = 1.0 if total == 0 else passed_count / total
    minimum_score = float(case.get("minimum_score", 0.8))
    return {
        "id": case.get("id", ""),
        "passed": score >= minimum_score,
        "score": round(score, 3),
        "minimum_score": minimum_score,
        "checks": checks,
    }


async def run_accountant_tests(base_url: str, *, auth_headers: dict[str, str] | None = None) -> dict[str, Any]:
    cases = load_accountant_cases()
    failures: list[str] = []
    case_results: list[dict[str, Any]] = []
    tests_run = 0

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=EVALUATOR_REQUEST_TIMEOUT_SECONDS,
        headers=auth_headers,
    ) as client:
        for case in cases:
            response = await client.post(
                "/api/v1/tasks",
                json={"input": case["input"], "context": {"evaluation_fixture": case["id"]}, "conversation_id": "accountant-eval"},
            )
            tests_run += 1
            if response.status_code != 200:
                failures.append(f"{case['id']}: task failed with status {response.status_code}")
                continue
            payload = response.json()
            answer = json.dumps(payload.get("brief", payload), sort_keys=True)
            result = score_accountant_answer(answer, case)
            tests_run += len(result["checks"])
            if not result["passed"]:
                failures.append(f"{case['id']}: score {result['score']} below {result['minimum_score']}")
            case_results.append(result)

    return {
        "passed": not failures,
        "tests": tests_run,
        "failures": failures,
        "cases": case_results,
    }
