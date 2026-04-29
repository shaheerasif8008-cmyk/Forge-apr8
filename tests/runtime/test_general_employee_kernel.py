from __future__ import annotations

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
