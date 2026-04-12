"""Evaluator suite for the executive assistant archetype."""

from __future__ import annotations

import httpx


async def run_executive_assistant_tests(base_url: str) -> dict[str, object]:
    tests_run = 0
    failures: list[str] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": "Please schedule a meeting with Sarah next week and draft a concise follow-up.",
                "context": {},
                "conversation_id": "default",
            },
        )
        tests_run += 1
        if response.status_code != 200:
            failures.append("Executive assistant task failed")
        else:
            brief = response.json().get("brief", {})
            if brief.get("title") != "Executive Assistant Update":
                failures.append("Executive assistant output missing task title")
            if not brief.get("schedule_updates"):
                failures.append("Executive assistant output missing schedule updates")

        meta = await client.get("/api/v1/meta")
        tests_run += 1
        if meta.status_code != 200 or meta.json().get("workflow") != "executive_assistant":
            failures.append("Meta endpoint did not expose executive assistant workflow")

    return {"passed": len(failures) == 0, "tests": tests_run, "failures": failures}
