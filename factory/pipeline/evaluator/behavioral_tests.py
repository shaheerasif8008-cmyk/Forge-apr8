"""Behavioral evaluator test suite."""

from __future__ import annotations

import httpx

from factory.pipeline.evaluator.deepeval_adapter import bias_metric, toxicity_metric
from tests.fixtures.sample_emails import AMBIGUOUS


async def run_behavioral_tests(base_url: str) -> dict[str, object]:
    """Exercise key employee app endpoints and score output behavior."""
    tests_run = 0
    failures: list[str] = []
    metrics: list[dict[str, object]] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        ambiguous = await client.post(
            "/api/v1/tasks",
            json={"input": AMBIGUOUS, "context": {"input_type": "email"}},
        )
        tests_run += 1
        summary_text = ""
        if ambiguous.status_code != 200:
            failures.append("Ambiguous intake failed")
        else:
            payload = ambiguous.json()
            decision = payload.get("brief", {}).get("analysis", {}).get("qualification_decision")
            summary_text = payload.get("brief", {}).get("executive_summary", "")
            if decision not in {"needs_review", "qualified"}:
                failures.append("Ambiguous intake returned unexpected decision")

        settings_put = await client.put("/api/v1/settings", json={"values": {"quiet_hours": "after_5pm"}})
        tests_run += 1
        if settings_put.status_code != 200 or settings_put.json().get("quiet_hours") != "after_5pm":
            failures.append("Settings update failed")

        approvals = await client.get("/api/v1/approvals")
        tests_run += 1
        if approvals.status_code != 200 or not isinstance(approvals.json(), list):
            failures.append("Approvals endpoint failed")

        metrics_response = await client.get("/api/v1/metrics")
        tests_run += 1
        payload = metrics_response.json() if metrics_response.status_code == 200 else {}
        if metrics_response.status_code != 200 or "tasks_total" not in payload:
            failures.append("Metrics endpoint failed")

        for metric in (toxicity_metric(summary_text), bias_metric(summary_text)):
            tests_run += 1
            metrics.append(metric.as_dict())
            if not metric.passed:
                failures.append(f"Behavioral metric failed: {metric.name}")

    return {"passed": len(failures) == 0, "tests": tests_run, "failures": failures, "metrics": metrics}
