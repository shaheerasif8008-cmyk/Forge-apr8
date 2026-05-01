from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
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
        self._task_lanes: dict[str, str] = {}
        self._last_task_id = ""

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, path: str, json: dict[str, object]) -> FakeResponse:
        self.requests.append({"path": path, "json": json})
        task_id = f"task-{len(self.requests)}"
        self._last_task_id = task_id
        if path.endswith("/corrections"):
            return FakeResponse(
                200,
                {
                    "task_id": path.split("/")[-2],
                    "correction_key": "baseline_correction",
                    "acknowledgement": "You're right. I misread that. Correcting now.",
                    "repeat_count": 1,
                },
            )
        if path == "/api/v1/autonomy/daily-loop":
            return FakeResponse(
                200,
                {
                    "run_id": "daily-loop-1",
                    "phases": [
                        {"name": "overnight_review"},
                        {"name": "morning_briefing"},
                        {"name": "active_hours"},
                        {"name": "wind_down"},
                    ],
                    "metrics": {"briefings_sent": 1, "wind_down_reports_sent": 1},
                },
            )
        context = json.get("context", {})
        fixture_id = context.get("evaluation_fixture", "") if isinstance(context, dict) else ""
        self._task_lanes[task_id] = {
            "knowledge_work": "knowledge_work",
            "business_process": "business_process",
            "hybrid": "hybrid",
        }.get(str(fixture_id), "hybrid")
        brief = {
            "title": "Baseline Result",
            "executive_summary": "Completed baseline task with evidence and action log.",
            "action_items": ["next step"],
        }
        return FakeResponse(200, {"task_id": task_id, "status": "completed", "brief": brief})

    async def get(self, path: str) -> FakeResponse:
        if path == "/api/v1/meta":
            return FakeResponse(
                200,
                {
                    "employee_name": "Avery",
                    "workflow": "executive_assistant",
                    "workflow_packs": ["executive_assistant_pack"],
                    "kernel_baseline": {
                        "version": "1.0.0",
                        "required_lanes": ["knowledge_work", "business_process", "hybrid"],
                        "certification_required": True,
                        "tool_action_boundary": "tool_broker",
                        "sovereign_export_required": True,
                    },
                },
            )
        if path.endswith("/metrics"):
            return FakeResponse(
                200,
                {
                    "roi": {
                        "estimated_minutes_saved": 75.0,
                        "completed_tasks": 3,
                        "escalations": 1,
                        "rework_events": 1,
                    },
                    "tasks_total": 3,
                },
            )
        if path == "/api/v1/corrections":
            return FakeResponse(200, [{"correction_key": "baseline_correction"}])
        if path == "/api/v1/memory/ops?category=local_learning&limit=20":
            return FakeResponse(200, [{"key": "learning:baseline_correction", "category": "local_learning"}])
        if path == "/api/v1/activity?limit=100":
            return FakeResponse(
                200,
                [
                    {"event_type": "output_produced", "details": {"confidence": 0.8}},
                    {"event_type": "reasoning_captured", "confidence": 0.8},
                    {"event_type": "tool_invoked", "details": {"tool_id": "email_tool"}},
                    {"event_type": "mistake_corrected", "details": {"correction_key": "baseline_correction"}},
                ],
            )
        if path == "/api/v1/runtime/recovery":
            return FakeResponse(
                200,
                {
                    "policy": {
                        "recovery_endpoint": "/api/v1/runtime/recovery",
                        "task_state_source": "employee_tasks",
                    },
                    "startup_summary": {"interrupted_task_ids": []},
                },
            )
        if "/tasks/" in path:
            task_id = path.rsplit("/", 1)[-1]
            lane = self._task_lanes.get(task_id, "hybrid")
            return FakeResponse(
                200,
                {
                    "workflow_output": {
                        "kernel": {
                            "task_lane": lane,
                            "plan": {
                                "steps": ["Understand requested outcome"],
                                "required_tools": ["email_tool"],
                                "approval_points": ["external_send"],
                                "completion_criteria": ["output_created", "audit_recorded", "roi_recorded"],
                            },
                            "classification": {"confidence": 0.86},
                            "execution": {
                                "lane_handler": lane,
                                "assembled_context": "TASK INPUT\nBaseline fixture context.",
                                "context_source": "context_assembler",
                                "tool_results": (
                                    [
                                        {
                                            "tool_id": "email_tool",
                                            "action": "check_inbox",
                                            "success": True,
                                        }
                                    ]
                                    if lane in {"business_process", "hybrid"}
                                    else []
                                ),
                                "deliverables": [{"type": "brief", "body": "Done"}],
                                "approval_required": lane == "hybrid",
                            },
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
    assert result["tests"] >= 14
    assert not result["failures"]


@pytest.mark.anyio
async def test_baseline_tests_pass_against_in_process_employee(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_employee_app(
        "baseline-avery",
        {
            "manifest": {
                "employee_id": "baseline-avery",
                "org_id": "org-1",
                "employee_name": "Avery",
                "role_title": "AI Operations Employee",
                "employee_type": "executive_assistant",
                "workflow": "executive_assistant",
                "workflow_packs": ["executive_assistant_pack", "operations_coordinator_pack"],
                "tool_permissions": ["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
                "identity_layers": {
                    "layer_1_core_identity": "You are a Forge AI Employee.",
                    "layer_2_role_definition": "You are Avery, AI Operations Employee.",
                    "layer_3_organizational_map": "Report to Operations Lead.",
                    "layer_4_behavioral_rules": "Ask before high-risk external sends.",
                    "layer_5_retrieved_context": "",
                    "layer_6_self_awareness": "You can plan knowledge work and process work.",
                },
                "components": [
                    {"id": "workflow_executor", "category": "work", "config": {}},
                    {"id": "communication_manager", "category": "work", "config": {}},
                    {"id": "scheduler_manager", "category": "work", "config": {}},
                    {"id": "email_tool", "category": "tools", "config": {}},
                    {"id": "calendar_tool", "category": "tools", "config": {}},
                    {"id": "messaging_tool", "category": "tools", "config": {}},
                    {"id": "crm_tool", "category": "tools", "config": {}},
                    {"id": "operational_memory", "category": "data", "config": {}},
                    {"id": "working_memory", "category": "data", "config": {}},
                    {"id": "context_assembler", "category": "data", "config": {}},
                    {"id": "org_context", "category": "data", "config": {}},
                    {"id": "audit_system", "category": "quality", "config": {}},
                    {"id": "explainability", "category": "quality", "config": {}},
                    {"id": "autonomy_manager", "category": "quality", "config": {}},
                    {"id": "input_protection", "category": "quality", "config": {}},
                ],
                "ui": {"app_badge": "Baseline", "capabilities": ["plan work", "execute workflows"]},
                "org_map": [],
            },
            "supervisor_email": "ops@example.com",
        },
    )

    monkeypatch.setattr(
        "factory.pipeline.evaluator.baseline_tests.httpx.AsyncClient",
        lambda **kwargs: AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
    )

    result = await run_baseline_tests("http://test")

    assert result["passed"] is True
    assert not result["failures"]
