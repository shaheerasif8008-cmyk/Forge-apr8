from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
from employee_runtime.core.kernel import (
    GeneralEmployeeKernel,
    classify_task,
    create_task_plan,
    estimate_roi,
    task_plan_to_context,
)
from employee_runtime.workflow_packs import get_workflow_pack


def test_classify_task_identifies_knowledge_work() -> None:
    result = classify_task("Prepare a concise investor update from these notes.", [])

    assert result.lane == "knowledge_work"
    assert result.confidence >= 0.7


def test_classify_task_identifies_business_process() -> None:
    result = classify_task("Update the CRM record, route approval, and notify the account owner.", [])

    assert result.lane == "business_process"
    assert result.confidence >= 0.7


def test_classify_task_identifies_hybrid_work() -> None:
    result = classify_task("Draft the client follow-up and schedule the review meeting.", [])

    assert result.lane == "hybrid"


def test_create_task_plan_uses_pack_template_and_approval_points() -> None:
    pack = get_workflow_pack("accounting_ops_pack")
    classification = classify_task("Review AP aging and draft follow-up for overdue invoices.", [pack])

    plan = create_task_plan(
        task_input="Review AP aging and draft follow-up for overdue invoices.",
        classification=classification,
        packs=[pack],
    )

    assert plan.lane == "hybrid"
    assert "Deliver professional output" in plan.steps
    assert "external_send" in plan.approval_points
    assert plan.output_template


def test_task_plan_to_context_is_serializable() -> None:
    pack = get_workflow_pack("operations_coordinator_pack")
    plan = create_task_plan(
        task_input="Update checklist and notify the owner.",
        classification=classify_task("Update checklist and notify the owner.", [pack]),
        packs=[pack],
    )

    context = task_plan_to_context(plan)

    assert context["kernel"]["task_lane"] in {"business_process", "hybrid"}
    assert context["kernel"]["plan"]["steps"]


def test_estimate_roi_uses_pack_minutes_saved() -> None:
    pack = get_workflow_pack("legal_intake_pack")

    roi = estimate_roi([pack], completed_tasks=2, escalations=1, rework_events=0)

    assert roi["estimated_minutes_saved"] == 80.0
    assert roi["completed_tasks"] == 2
    assert roi["escalations"] == 1


class FakeContextAssembler:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def assemble(
        self,
        task_input: str,
        employee_id: str,
        org_id: str,
        conversation_id: str,
        token_budget: int = 8000,
    ) -> str:
        self.calls.append(
            {
                "task_input": task_input,
                "employee_id": employee_id,
                "org_id": org_id,
                "conversation_id": conversation_id,
                "token_budget": token_budget,
            }
        )
        return "ORG CONTEXT\nSupervisor: Riley\n\nRECENT CONVERSATION\nuser: previous task"


class FakeToolBroker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, tool_id: str, action: str, **params: object) -> object:
        self.calls.append({"tool_id": tool_id, "action": action, "params": params})
        return type(
            "Result",
            (),
            {
                "success": True,
                "data": {
                    "id": "tool-result-1",
                    "tool_id": tool_id,
                    "action": action,
                },
            },
        )()


@pytest.mark.anyio
async def test_general_employee_kernel_runs_knowledge_lane_with_assembled_context() -> None:
    assembler = FakeContextAssembler()
    kernel = GeneralEmployeeKernel(
        employee_id="kernel-avery",
        org_id="org-1",
        packs=[get_workflow_pack("executive_assistant_pack")],
        components={"context_assembler": assembler},
    )

    result = await kernel.execute_task(
        "Prepare a concise investor update from these notes.",
        input_type="chat",
        request_context={},
        conversation_id="conv-1",
        task_id="task-1",
    )

    execution = result["workflow_output"]["kernel"]["execution"]
    assert result["workflow_output"]["kernel"]["task_lane"] == "knowledge_work"
    assert execution["lane_handler"] == "knowledge_work"
    assert execution["context_source"] == "context_assembler"
    assert "ORG CONTEXT" in execution["assembled_context"]
    assert result["result_card"]["sections"]
    assert result["requires_human_approval"] is False
    assert assembler.calls[0]["conversation_id"] == "conv-1"


@pytest.mark.anyio
async def test_general_employee_kernel_runs_business_process_lane_through_tool_broker() -> None:
    broker = FakeToolBroker()
    kernel = GeneralEmployeeKernel(
        employee_id="kernel-avery",
        org_id="org-1",
        packs=[get_workflow_pack("operations_coordinator_pack")],
        components={"context_assembler": FakeContextAssembler()},
        tool_broker=broker,
    )

    result = await kernel.execute_task(
        "Update the checklist, route approval, and notify the account owner.",
        input_type="chat",
        request_context={},
        conversation_id="conv-1",
        task_id="task-2",
    )

    execution = result["workflow_output"]["kernel"]["execution"]
    assert result["workflow_output"]["kernel"]["task_lane"] == "business_process"
    assert execution["lane_handler"] == "business_process"
    assert execution["tool_results"]
    assert broker.calls
    assert broker.calls[0]["tool_id"] in {"email_tool", "messaging_tool", "custom_api_tool"}
    assert result["requires_human_approval"] is True


def _kernel_manifest() -> dict[str, object]:
    return {
        "manifest": {
            "employee_id": "kernel-avery",
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
        }
    }


@pytest.mark.anyio
async def test_runtime_persists_kernel_plan_and_roi_metadata() -> None:
    app = create_employee_app("kernel-avery", _kernel_manifest())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": "Draft the client update, update the CRM record, and notify the account owner.",
                "context": {},
                "conversation_id": "default",
            },
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        task = (await client.get(f"/api/v1/tasks/{task_id}")).json()
        metrics = (await client.get("/api/v1/metrics")).json()

    kernel = task["workflow_output"]["kernel"]
    assert kernel["task_lane"] == "hybrid"
    assert kernel["plan"]["required_tools"]
    assert kernel["execution"]["lane_handler"] == "hybrid"
    assert kernel["execution"]["context_source"] == "context_assembler"
    assert metrics["roi"]["estimated_minutes_saved"] > 0


@pytest.mark.anyio
async def test_runtime_meta_exposes_kernel_certification_contract() -> None:
    app = create_employee_app("kernel-avery", _kernel_manifest())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_packs"] == ["executive_assistant_pack", "operations_coordinator_pack"]
    assert payload["kernel_baseline"]["required_lanes"] == ["knowledge_work", "business_process", "hybrid"]
    assert payload["kernel_baseline"]["tool_action_boundary"] == "tool_broker"
    assert payload["kernel_baseline"]["sovereign_export_required"] is True
