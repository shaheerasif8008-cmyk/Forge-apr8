from __future__ import annotations

from component_library.work.workflow_executor import WorkflowExecutor


def test_workflow_executor_creates_accounting_actions_from_aging_input() -> None:
    executor = WorkflowExecutor()
    plan = executor.plan(
        "Review AP aging: INV-102 is 45 days overdue for $12,400, "
        "INV-104 is 12 days overdue for $1,980."
    )

    assert plan.finance_actions
    assert plan.finance_metrics["overdue_invoice_count"] == 2.0
    assert plan.finance_metrics["total_overdue_amount"] == 14380.0
    assert "INV-102" in plan.finance_actions[0]
    assert plan.requires_approval is True
    assert "totaling $14,380.00" in plan.summary
