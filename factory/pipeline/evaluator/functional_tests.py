"""Functional evaluator test suite."""

from __future__ import annotations

import httpx

from tests.fixtures.sample_emails import CLEAR_QUALIFIED, CLEAR_UNQUALIFIED


async def run_functional_tests(base_url: str) -> dict[str, object]:
    """Submit representative intake tasks and verify expected outputs."""
    tests_run = 0
    failures: list[str] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        history = await client.get("/api/v1/chat/history")
        tests_run += 1
        if history.status_code != 200:
            failures.append("Chat history endpoint unavailable")

        qualified = await client.post(
            "/api/v1/tasks",
            json={"input": CLEAR_QUALIFIED, "context": {"input_type": "email"}, "conversation_id": "default"},
        )
        tests_run += 1
        if qualified.status_code != 200:
            failures.append("Qualified intake task failed")
        else:
            payload = qualified.json()
            brief = payload.get("brief", {})
            analysis = brief.get("analysis", {})
            for field in ("client_info", "analysis", "confidence_score"):
                tests_run += 1
                if field not in brief:
                    failures.append(f"Brief missing field: {field}")
            if analysis.get("qualification_decision") != "qualified":
                failures.append("Qualified intake did not return qualified decision")

        unqualified = await client.post(
            "/api/v1/tasks",
            json={"input": CLEAR_UNQUALIFIED, "context": {"input_type": "email"}},
        )
        tests_run += 1
        if unqualified.status_code != 200:
            failures.append("Unqualified intake task failed")
        else:
            brief = unqualified.json().get("brief", {})
            analysis = brief.get("analysis", {})
            if analysis.get("qualification_decision") != "not_qualified":
                failures.append("Unqualified intake did not return not_qualified decision")

    return {"passed": len(failures) == 0, "tests": tests_run, "failures": failures}
