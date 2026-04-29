from __future__ import annotations

from component_library.work.communication_manager import CommunicationManager
from component_library.work.schemas import ExecutiveAssistantPlan


def test_communication_manager_returns_accounting_update_for_finance_plan() -> None:
    manager = CommunicationManager()
    manager._signature = "Finley"  # type: ignore[attr-defined]

    plan = ExecutiveAssistantPlan(
        summary="General summary",
        requested_actions=["triage request"],
        finance_actions=["Send payment follow-up for INV-102 ($12,400.00, 45 days overdue)"],
        finance_summary="AP/AR aging parsed: 1 overdue invoice totaling $12,400.00.",
        requires_approval=True,
    )

    result = manager.compose(plan)
    assert result.title == "Accounting Operations Update"
    assert result.finance_actions
    assert "INV-102" in result.drafted_response
    assert result.confidence_score == 0.73
