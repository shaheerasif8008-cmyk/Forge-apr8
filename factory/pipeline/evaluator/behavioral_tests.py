"""Behavioral evaluator test suite."""

from __future__ import annotations

import os

import httpx

from factory.pipeline.evaluator.deepeval_adapter import bias_metric, toxicity_metric
from tests.fixtures.sample_emails import AMBIGUOUS

EVALUATOR_REQUEST_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_REQUEST_TIMEOUT_SECONDS", "300"))


async def run_behavioral_tests(base_url: str, *, auth_headers: dict[str, str] | None = None) -> dict[str, object]:
    """Exercise key employee app endpoints and score output behavior."""
    tests_run = 0
    failures: list[str] = []
    metrics: list[dict[str, object]] = []

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=EVALUATOR_REQUEST_TIMEOUT_SECONDS,
        headers=auth_headers,
    ) as client:
        try:
            meta = await client.get("/api/v1/meta")
            workflow = meta.json().get("workflow", "") if meta.status_code == 200 else ""
        except Exception:  # noqa: BLE001
            workflow = ""
        behavioral_input = (
            "We have a novel vendor notice with unclear accounting impact. Please propose options before taking action."
            if workflow == "executive_assistant"
            else AMBIGUOUS
        )
        ambiguous = await client.post(
            "/api/v1/tasks",
            json={"input": behavioral_input, "context": {"input_type": "email"}},
        )
        tests_run += 1
        summary_text = ""
        if ambiguous.status_code != 200:
            failures.append("Ambiguous intake failed")
        else:
            payload = ambiguous.json()
            summary_text = payload.get("brief", {}).get("executive_summary", "")
            decision = payload.get("brief", {}).get("analysis", {}).get("qualification_decision")
            if workflow == "executive_assistant":
                options = payload.get("brief", {}).get("novel_options", [])
                option_labels = " ".join(str(option).lower() for option in options)
                required_option_signals = ("safe", "fast", "creative")
                if len(options) < 3 or not all(signal in option_labels for signal in required_option_signals):
                    failures.append("Novel executive task did not offer safe/fast/creative options")
            elif decision not in {"needs_review", "qualified"}:
                failures.append("Ambiguous intake returned unexpected decision")

        settings_put = await client.put("/api/v1/settings", json={"values": {"quiet_hours": "after_5pm"}})
        tests_run += 1
        if settings_put.status_code != 200 or settings_put.json().get("quiet_hours") != "after_5pm":
            failures.append("Settings update failed")

        approvals = await client.get("/api/v1/approvals")
        tests_run += 1
        approval_payload = approvals.json() if approvals.status_code == 200 else None
        if approvals.status_code != 200 or not isinstance(approval_payload, list):
            failures.append("Approvals endpoint failed")
        else:
            malformed_approvals = [
                approval
                for approval in approval_payload
                if not isinstance(approval, dict)
                or not (approval.get("id") or approval.get("message_id") or approval.get("task_id"))
                or not (approval.get("status") or approval.get("decision"))
            ]
            if malformed_approvals:
                failures.append("Approvals endpoint returned malformed approval records")

        metrics_response = await client.get("/api/v1/metrics")
        tests_run += 1
        payload = metrics_response.json() if metrics_response.status_code == 200 else {}
        if (
            metrics_response.status_code != 200
            or not isinstance(payload.get("tasks_total"), int | float)
            or payload.get("tasks_total", -1) < 0
        ):
            failures.append("Metrics endpoint failed")

        for metric in (toxicity_metric(summary_text), bias_metric(summary_text)):
            tests_run += 1
            metrics.append(metric.as_dict())
            if not metric.passed:
                failures.append(f"Behavioral metric failed: {metric.name}")

    return {"passed": len(failures) == 0, "tests": tests_run, "failures": failures, "metrics": metrics}
