from __future__ import annotations

import pytest

from factory.pipeline.evaluator.baseline_tests import run_baseline_tests


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.tasks: dict[str, str] = {}

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, path: str, json: dict[str, object]) -> FakeResponse:
        self.requests.append({"path": path, "json": json})
        task_id = f"task-{len(self.requests)}"
        context = json.get("context", {})
        fixture = context.get("evaluation_fixture", "") if isinstance(context, dict) else ""
        self.tasks[task_id] = str(fixture)
        brief = {
            "title": "Baseline Result",
            "executive_summary": "Completed baseline task with evidence and action log.",
            "action_items": ["next step"],
        }
        return FakeResponse(200, {"task_id": task_id, "status": "completed", "brief": brief})

    async def get(self, path: str) -> FakeResponse:
        if path.endswith("/metrics"):
            return FakeResponse(200, {"roi": {"estimated_minutes_saved": 75.0}, "tasks_total": 3})
        if "/tasks/" in path:
            fixture = self.tasks.get(path.rsplit("/", 1)[-1], "")
            lane = {
                "knowledge_work": "knowledge_work",
                "business_process": "business_process",
                "hybrid": "hybrid",
            }.get(fixture, "hybrid")
            return FakeResponse(
                200,
                {
                    "workflow_output": {
                        "kernel": {
                            "task_lane": lane,
                            "plan": {"steps": ["Understand requested outcome"]},
                        }
                    },
                    "result_card": {"executive_summary": "Done"},
                },
            )
        return FakeResponse(200, {})


@pytest.mark.anyio
async def test_baseline_tests_require_kernel_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("factory.pipeline.evaluator.baseline_tests.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = await run_baseline_tests("http://test", auth_headers={"Authorization": "Bearer token"})

    assert result["passed"] is True
    assert result["tests"] >= 6
    assert not result["failures"]
