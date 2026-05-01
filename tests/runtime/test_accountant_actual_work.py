from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app
from employee_runtime.workflows.dynamic_builder import _maybe_run_accounting_advisory


class FakeAccountingModel:
    async def complete(self, messages, **kwargs):  # noqa: ANN001, ANN003
        assert kwargs["temperature"] == 0.0
        assert "accounting advisory capability" in kwargs["system"]
        assert "ASC 606" in messages[0]["content"]
        return "ASC 606 five steps: identify the contract, identify performance obligations, determine transaction price, allocate price, recognize revenue."


@pytest.mark.anyio
async def test_accounting_advisory_uses_packaged_model_component() -> None:
    result = await _maybe_run_accounting_advisory(
        "Under ASC 606, list the five-step model for revenue recognition.",
        {
            "identity_layers": {
                "layer_2_role_definition": "You are Finley, AI Accountant.",
            }
        },
        {"litellm_router": FakeAccountingModel()},
    )

    plan = result["workflow_output"]["plan"]
    assert "ASC 606 five steps" in plan["finance_summary"]
    assert plan["finance_actions"]
    assert result["requires_human_approval"] is False


class FailingAccountingModel:
    async def complete(self, messages, **kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError("model unavailable")


class PartialAccountingModel:
    async def complete(self, messages, **kwargs):  # noqa: ANN001, ANN003
        return (
            "ASC 606 five steps: identify the contract, identify performance obligations, "
            "determine transaction price, allocate price, recognize revenue. "
            "This should be reviewed by a qualified human."
        )


@pytest.mark.anyio
async def test_accounting_advisory_fallback_handles_multi_part_accounting_cases() -> None:
    result = await _maybe_run_accounting_advisory(
        (
            "Under ASC 606 list the five steps, calculate weighted-average inventory COGS and ending inventory, "
            "and classify an ASC 842 lease."
        ),
        {"identity_layers": {"layer_2_role_definition": "You are Finley, AI Accountant."}},
        {"litellm_router": FailingAccountingModel()},
    )

    finance_summary = result["workflow_output"]["plan"]["finance_summary"]
    assert "$3,666.67" in finance_summary
    assert "$1,833.33" in finance_summary
    assert "Operating lease" in finance_summary


@pytest.mark.anyio
async def test_accounting_advisory_augments_partial_model_answer_for_required_accounting_work() -> None:
    result = await _maybe_run_accounting_advisory(
        (
            "Under ASC 606 list the five steps, calculate weighted-average inventory COGS and ending inventory, "
            "and classify an ASC 842 lease."
        ),
        {"identity_layers": {"layer_2_role_definition": "You are Finley, AI Accountant."}},
        {"litellm_router": PartialAccountingModel()},
    )

    finance_summary = result["workflow_output"]["plan"]["finance_summary"]
    assert "ASC 606" in finance_summary
    assert "$3,666.67" in finance_summary
    assert "$1,833.33" in finance_summary
    assert "Operating lease" in finance_summary


@pytest.mark.anyio
async def test_accountant_employee_executes_ap_aging_workflow() -> None:
    app = create_employee_app(
        "finley",
        {
            "manifest": {
                "employee_id": "finley",
                "org_id": "org-1",
                "employee_name": "Finley",
                "role_title": "AI Accountant",
                "employee_type": "executive_assistant",
                "workflow": "executive_assistant",
                "tool_permissions": ["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
                "identity_layers": {
                    "layer_1_core_identity": "You are a Forge AI Employee.",
                    "layer_2_role_definition": "You are Finley, AI Accountant.",
                    "layer_3_organizational_map": "Report to Controller.",
                    "layer_4_behavioral_rules": "Escalate high-risk cash collections.",
                    "layer_5_retrieved_context": "",
                    "layer_6_self_awareness": "You can execute AP/AR follow-ups and drafts.",
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
                    {"id": "input_protection", "category": "quality", "config": {}},
                ],
                "ui": {
                    "app_badge": "Hosted web",
                    "capabilities": ["run AP/AR follow-ups", "prepare close updates"],
                },
                "org_map": [],
            }
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": (
                    "Review AP aging list and draft follow-up actions: "
                    "INV-102 is 45 days overdue for $12,400, INV-104 is 12 days overdue for $1,980."
                ),
                "context": {},
                "conversation_id": "default",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"]["title"] == "Accounting Operations Update"
    assert payload["brief"]["finance_actions"]
    assert payload["brief"]["finance_metrics"]["total_overdue_amount"] == 14380.0
    assert "INV-102" in payload["brief"]["drafted_response"]
