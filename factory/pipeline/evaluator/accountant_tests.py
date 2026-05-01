"""Evaluator suite for accountant employees."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "accountant_tasks.jsonl"
EVALUATOR_REQUEST_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_REQUEST_TIMEOUT_SECONDS", "300"))


def load_accountant_cases(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace(",", "").split())


def _parse_number(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    cleaned = str(value).strip().replace("$", "").replace(",", "").replace("%", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    return float(cleaned)


def _numbers_in_answer(answer: str) -> list[float]:
    matches = re.findall(r"\(?-?\$?\d[\d,]*(?:\.\d+)?%?\)?", answer)
    numbers: list[float] = []
    for match in matches:
        try:
            numbers.append(_parse_number(match))
        except ValueError:
            continue
    return numbers


def score_accountant_answer(answer: str, case: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_text(answer)
    answer_numbers = _numbers_in_answer(answer)
    checks: list[dict[str, Any]] = []
    passed_count = 0
    for check in case.get("checks", []):
        all_of = [_normalize_text(str(term)) for term in check.get("all_of", [])]
        any_of = [_normalize_text(str(term)) for term in check.get("any_of", [])]
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

    evidence_results: list[dict[str, Any]] = []
    required_evidence = [_normalize_text(str(term)) for term in case.get("required_evidence", [])]
    if required_evidence:
        missing_evidence = [term for term in required_evidence if term not in normalized]
        evidence_passed = not missing_evidence
        if evidence_passed:
            passed_count += 1
        evidence_results.append(
            {
                "id": "required_evidence",
                "passed": evidence_passed,
                "missing_all": missing_evidence,
            }
        )

    numeric_results: list[dict[str, Any]] = []
    for numeric_answer in case.get("numeric_answers", []):
        expected = _parse_number(numeric_answer["value"])
        tolerance = abs(_parse_number(numeric_answer.get("tolerance", 0.01)))
        matched_value = next((value for value in answer_numbers if abs(value - expected) <= tolerance), None)
        passed = matched_value is not None
        if passed:
            passed_count += 1
        numeric_results.append(
            {
                "id": numeric_answer.get("id", ""),
                "passed": passed,
                "expected": expected,
                "tolerance": tolerance,
                "matched_value": matched_value,
            }
        )

    total = len(checks) + len(evidence_results) + len(numeric_results)
    score = 1.0 if total == 0 else passed_count / total
    minimum_score = float(case.get("minimum_score", 0.8))
    return {
        "id": case.get("id", ""),
        "passed": score >= minimum_score,
        "score": round(score, 3),
        "minimum_score": minimum_score,
        "checks": checks,
        "evidence": evidence_results,
        "numeric_answers": numeric_results,
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
