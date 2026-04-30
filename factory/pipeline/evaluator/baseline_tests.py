from __future__ import annotations

from typing import Any

import httpx

BASELINE_CASES = [
    {
        "id": "knowledge_work",
        "input": "Prepare a concise client-ready update with assumptions and next steps.",
        "expected_lane": "knowledge_work",
    },
    {
        "id": "business_process",
        "input": "Update the checklist, route approval, and notify the account owner.",
        "expected_lane": "business_process",
    },
    {
        "id": "hybrid",
        "input": "Draft the client follow-up, schedule the review meeting, and update the CRM record.",
        "expected_lane": "hybrid",
    },
]


async def run_baseline_tests(
    base_url: str,
    *,
    auth_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    tests_run = 0
    async with httpx.AsyncClient(base_url=base_url, timeout=120, headers=auth_headers) as client:
        for case in BASELINE_CASES:
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "input": case["input"],
                    "context": {"evaluation_fixture": case["id"]},
                    "conversation_id": "baseline-eval",
                },
            )
            tests_run += 1
            if response.status_code != 200:
                failures.append(f"{case['id']}: task returned HTTP {response.status_code}")
                continue
            task_id = str(response.json().get("task_id", ""))
            task_response = await client.get(f"/api/v1/tasks/{task_id}")
            tests_run += 1
            if task_response.status_code != 200:
                failures.append(f"{case['id']}: task status returned HTTP {task_response.status_code}")
                continue
            task = task_response.json()
            kernel = task.get("workflow_output", {}).get("kernel", {})
            lane = str(kernel.get("task_lane", ""))
            if lane != case["expected_lane"]:
                failures.append(f"{case['id']}: expected lane {case['expected_lane']} got {lane}")
            if not kernel.get("plan", {}).get("steps"):
                failures.append(f"{case['id']}: missing kernel plan steps")
            if not task.get("result_card") and not response.json().get("brief"):
                failures.append(f"{case['id']}: missing professional output card")

        metrics_response = await client.get("/api/v1/metrics")
        tests_run += 1
        if metrics_response.status_code != 200:
            failures.append(f"metrics: returned HTTP {metrics_response.status_code}")
        else:
            metrics = metrics_response.json()
            if metrics.get("roi", {}).get("estimated_minutes_saved", 0) <= 0:
                failures.append("metrics: missing positive ROI estimate")

    return {"passed": not failures, "tests": tests_run, "failures": failures, "cases": BASELINE_CASES}
