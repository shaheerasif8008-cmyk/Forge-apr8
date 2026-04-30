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


async def run_baseline_tests(base_url: str, *, auth_headers: dict[str, str] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    tests_run = 0
    last_task_id = ""
    async with httpx.AsyncClient(base_url=base_url, timeout=120, headers=auth_headers) as client:
        meta_response = await client.get("/api/v1/meta")
        tests_run += 1
        if meta_response.status_code != 200:
            failures.append(f"meta: returned HTTP {meta_response.status_code}")
        else:
            _validate_meta_contract(meta_response.json(), failures)

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
            last_task_id = task_id
            task_response = await client.get(f"/api/v1/tasks/{task_id}")
            tests_run += 1
            if task_response.status_code != 200:
                failures.append(f"{case['id']}: task status returned HTTP {task_response.status_code}")
                continue

            task = task_response.json()
            kernel = task.get("workflow_output", {}).get("kernel", {})
            _validate_kernel_task_contract(case, kernel, failures)
            if not task.get("result_card") and not response.json().get("brief"):
                failures.append(f"{case['id']}: missing professional output card")

        if last_task_id:
            correction_response = await client.post(
                f"/api/v1/tasks/{last_task_id}/corrections",
                json={
                    "message": "Use the approved baseline correction rule going forward.",
                    "corrected_output": "Apply the approved correction rule.",
                },
            )
            tests_run += 1
            if correction_response.status_code != 200:
                failures.append(f"correction: returned HTTP {correction_response.status_code}")

            corrections_response = await client.get("/api/v1/corrections")
            tests_run += 1
            corrections = corrections_response.json() if corrections_response.status_code == 200 else []
            if corrections_response.status_code != 200 or not corrections:
                failures.append("correction: persisted correction was not listed")

            memory_response = await client.get("/api/v1/memory/ops?category=local_learning&limit=20")
            tests_run += 1
            memory = memory_response.json() if memory_response.status_code == 200 else []
            if memory_response.status_code != 200 or not memory:
                failures.append("correction: local learning memory was not persisted")

        daily_loop_response = await client.post(
            "/api/v1/autonomy/daily-loop",
            json={"conversation_id": "baseline-eval", "max_items": 2},
        )
        tests_run += 1
        if daily_loop_response.status_code != 200:
            failures.append(f"daily_loop: returned HTTP {daily_loop_response.status_code}")
        else:
            _validate_daily_loop_contract(daily_loop_response.json(), failures)

        activity_response = await client.get("/api/v1/activity?limit=100")
        tests_run += 1
        activity = activity_response.json() if activity_response.status_code == 200 else []
        if activity_response.status_code != 200:
            failures.append(f"activity: returned HTTP {activity_response.status_code}")
        else:
            _validate_activity_contract(activity, failures)

        recovery_response = await client.get("/api/v1/runtime/recovery")
        tests_run += 1
        if recovery_response.status_code != 200:
            failures.append(f"recovery: returned HTTP {recovery_response.status_code}")
        else:
            _validate_recovery_contract(recovery_response.json(), failures)

        metrics_response = await client.get("/api/v1/metrics")
        tests_run += 1
        if metrics_response.status_code != 200:
            failures.append(f"metrics: returned HTTP {metrics_response.status_code}")
        else:
            _validate_metrics_contract(metrics_response.json(), failures)

    return {
        "passed": not failures,
        "tests": tests_run,
        "failures": failures,
        "cases": BASELINE_CASES,
    }


def _validate_meta_contract(meta: Any, failures: list[str]) -> None:
    if not isinstance(meta, dict):
        failures.append("meta: response was not an object")
        return
    if not meta.get("workflow_packs"):
        failures.append("meta: missing workflow packs")
    baseline = meta.get("kernel_baseline", {})
    if not isinstance(baseline, dict):
        failures.append("meta: missing kernel baseline")
        return
    if baseline.get("required_lanes") != ["knowledge_work", "business_process", "hybrid"]:
        failures.append("meta: kernel baseline required lanes are incomplete")
    if baseline.get("tool_action_boundary") != "tool_broker":
        failures.append("meta: tool action boundary is not ToolBroker")
    if baseline.get("sovereign_export_required") is not True:
        failures.append("meta: sovereign export is not marked required")


def _validate_kernel_task_contract(case: dict[str, Any], kernel: Any, failures: list[str]) -> None:
    if not isinstance(kernel, dict):
        failures.append(f"{case['id']}: missing kernel metadata")
        return
    lane = str(kernel.get("task_lane", ""))
    if lane != case["expected_lane"]:
        failures.append(f"{case['id']}: expected lane {case['expected_lane']} got {lane}")
    plan = kernel.get("plan", {})
    if not isinstance(plan, dict):
        failures.append(f"{case['id']}: missing kernel plan")
        return
    if not plan.get("steps"):
        failures.append(f"{case['id']}: missing kernel plan steps")
    if case["expected_lane"] in {"business_process", "hybrid"} and not plan.get("required_tools"):
        failures.append(f"{case['id']}: missing required tools")
    if not plan.get("completion_criteria"):
        failures.append(f"{case['id']}: missing completion criteria")
    if case["expected_lane"] == "hybrid" and "external_send" not in plan.get("approval_points", []):
        failures.append(f"{case['id']}: missing approval point for external action")
    classification = kernel.get("classification", {})
    if isinstance(classification, dict) and float(classification.get("confidence", 1.0) or 0.0) < 0.7:
        if "low_confidence_clarification" not in plan.get("approval_points", []):
            failures.append(f"{case['id']}: low-confidence plan did not request clarification")


def _validate_activity_contract(activity: Any, failures: list[str]) -> None:
    if not isinstance(activity, list):
        failures.append("activity: response was not a list")
        return
    event_types = {str(event.get("event_type", "")) for event in activity if isinstance(event, dict)}
    if not ({"output_produced", "reasoning_captured"} & event_types):
        failures.append("activity: missing output or reasoning evidence")
    if "tool_invoked" not in event_types:
        failures.append("activity: missing ToolBroker invocation evidence")
    if "mistake_corrected" not in event_types:
        failures.append("activity: missing correction audit evidence")


def _validate_daily_loop_contract(report: Any, failures: list[str]) -> None:
    if not isinstance(report, dict):
        failures.append("daily_loop: response was not an object")
        return
    phase_names = {str(phase.get("name", "")) for phase in report.get("phases", []) if isinstance(phase, dict)}
    required = {"overnight_review", "morning_briefing", "active_hours", "wind_down"}
    missing = required - phase_names
    if missing:
        failures.append(f"daily_loop: missing phases {sorted(missing)}")
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict) or "briefings_sent" not in metrics or "wind_down_reports_sent" not in metrics:
        failures.append("daily_loop: missing briefing or wind-down metrics")


def _validate_recovery_contract(recovery: Any, failures: list[str]) -> None:
    if not isinstance(recovery, dict):
        failures.append("recovery: response was not an object")
        return
    policy = recovery.get("policy", {})
    if not isinstance(policy, dict):
        failures.append("recovery: missing policy")
        return
    if policy.get("recovery_endpoint") != "/api/v1/runtime/recovery":
        failures.append("recovery: missing runtime recovery endpoint")
    if policy.get("task_state_source") != "employee_tasks":
        failures.append("recovery: task state is not persisted to employee_tasks")


def _validate_metrics_contract(metrics: Any, failures: list[str]) -> None:
    if not isinstance(metrics, dict):
        failures.append("metrics: response was not an object")
        return
    roi = metrics.get("roi", {})
    if not isinstance(roi, dict):
        failures.append("metrics: missing ROI object")
        return
    if roi.get("estimated_minutes_saved", 0) <= 0:
        failures.append("metrics: missing positive ROI estimate")
    for key in ("completed_tasks", "escalations", "rework_events"):
        if key not in roi:
            failures.append(f"metrics: ROI missing {key}")
