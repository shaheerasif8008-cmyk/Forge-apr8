from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
from employee_runtime.core.kernel import classify_task, create_task_plan, estimate_roi, task_plan_to_context
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
