from __future__ import annotations

import pytest

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.quality.approval_manager import ApprovalManager
from component_library.quality.input_protection import InputProtection
from component_library.work.data_analyzer import DataAnalyzer
from component_library.work.draft_generator import DraftGenerator
from component_library.work.workflow_executor import WorkflowExecutor
from employee_runtime.core.engine import EmployeeEngine
from employee_runtime.workflows.dynamic_builder import condition_to_callable


class MockMergeComponent(WorkCapability):
    component_id = "mock"
    version = "1.0.0"

    def __init__(self, output: dict) -> None:
        self.output = output

    async def initialize(self, config: dict) -> None:
        return None

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return []

    async def execute(self, input_data):
        return self.output


@pytest.mark.anyio
async def test_dynamic_workflow_runs_end_to_end() -> None:
    spec = {
        "nodes": [
            {"node_id": "start_node", "component_id": "extractor", "config": {}},
            {"node_id": "scorer", "component_id": "scorer", "config": {}},
            {"node_id": "terminal", "custom_spec_id": "builtin_log_completion", "config": {"adapter": "builtin_log_completion"}},
        ],
        "edges": [
            {"from_node": "start_node", "to_node": "scorer", "condition": None},
            {"from_node": "scorer", "to_node": "terminal", "condition": None},
        ],
        "entry": "start_node",
        "terminals": ["terminal"],
    }
    components = {
        "extractor": MockMergeComponent({"foo": "bar"}),
        "scorer": MockMergeComponent({"confidence_report": {"overall_score": 0.9}}),
    }
    engine = EmployeeEngine(
        "dynamic",
        components,
        {"employee_id": "emp-1", "org_id": "org-1", "workflow_graph": spec},
    )
    result = await engine.process_task("hello")
    assert result["workflow_output"]["foo"] == "bar"
    assert result["confidence_report"]["overall_score"] == 0.9
    assert result["completed_at"]


@pytest.mark.anyio
async def test_dynamic_workflow_conditional_route() -> None:
    spec = {
        "nodes": [
            {"node_id": "score", "component_id": "scorer", "config": {}},
            {"node_id": "approve", "component_id": "approve", "config": {}},
            {"node_id": "review", "component_id": "review", "config": {}},
        ],
        "edges": [
            {"from_node": "score", "to_node": "approve", "condition": "confidence_report.overall_score >= 0.7"},
            {"from_node": "score", "to_node": "review", "condition": None},
        ],
        "entry": "score",
        "terminals": ["approve", "review"],
    }
    components = {
        "scorer": MockMergeComponent({"confidence_report": {"overall_score": 0.4}}),
        "approve": MockMergeComponent({"mode": "approved"}),
        "review": MockMergeComponent({"mode": "review"}),
    }
    engine = EmployeeEngine("dynamic", components, {"employee_id": "emp-1", "org_id": "org-1", "workflow_graph": spec})
    result = await engine.process_task("hello")
    assert result["workflow_output"]["mode"] == "review"


def test_unknown_condition_operator_raises() -> None:
    with pytest.raises(ValueError):
        condition_to_callable("score ~= 0.7")


@pytest.mark.anyio
async def test_accounting_ops_workflow_adapters_run_end_to_end() -> None:
    components = {
        "input_protection": InputProtection(),
        "workflow_executor": WorkflowExecutor(),
        "data_analyzer": DataAnalyzer(),
        "draft_generator": DraftGenerator(),
        "approval_manager": ApprovalManager(),
    }
    for component in components.values():
        await component.initialize({})

    spec = {
        "nodes": [
            {"node_id": "sanitize_input", "component_id": "input_protection", "config": {"adapter": "sanitize_input"}},
            {"node_id": "plan_close_work", "component_id": "workflow_executor", "config": {"adapter": "accounting_close_plan"}},
            {"node_id": "reconcile_bank_feed", "component_id": "data_analyzer", "config": {"adapter": "bank_feed_gl_reconciliation"}},
            {"node_id": "explain_variances", "component_id": "data_analyzer", "config": {"adapter": "variance_analysis"}},
            {"node_id": "draft_statements", "component_id": "draft_generator", "config": {"adapter": "statement_draft"}},
            {"node_id": "request_finance_approval", "component_id": "approval_manager", "config": {"adapter": "finance_approval_boundary"}},
            {"node_id": "deliver", "custom_spec_id": "builtin_deliver", "config": {"adapter": "builtin_deliver"}},
            {"node_id": "log_completion", "custom_spec_id": "builtin_log_completion", "config": {"adapter": "builtin_log_completion"}},
        ],
        "edges": [
            {"from_node": "sanitize_input", "to_node": "plan_close_work"},
            {"from_node": "plan_close_work", "to_node": "reconcile_bank_feed"},
            {"from_node": "reconcile_bank_feed", "to_node": "explain_variances"},
            {"from_node": "explain_variances", "to_node": "draft_statements"},
            {"from_node": "draft_statements", "to_node": "request_finance_approval"},
            {"from_node": "request_finance_approval", "to_node": "deliver"},
            {"from_node": "deliver", "to_node": "log_completion"},
        ],
        "entry": "sanitize_input",
        "terminals": ["log_completion"],
    }
    engine = EmployeeEngine(
        "accounting_ops",
        components,
        {"employee_id": "finley", "org_id": "org-1", "workflow_graph": spec},
    )
    result = await engine.process_task(
        "Prepare the month-end close package and reconcile cash.",
        metadata={
            "source_csvs": {
                "bank_feed": "date,description,amount\n2026-03-31,Ending balance,10100\n",
                "general_ledger": "account,balance\nCash,10500\nRevenue,-42000\n",
                "ap_aging": "vendor,invoice,days_past_due,amount\nAtlas,INV-102,45,12400\n",
                "ar_aging": "customer,invoice,days_past_due,amount\nNimbus,AR-201,33,8800\n",
            }
        },
    )

    assert result["workflow_output"]["close_metrics"]["cash_reconciliation_difference"] == -400.0
    assert result["result_card"]["title"] == "Accounting Operations Update"
    assert result["requires_human_approval"] is True
    assert result["completed_at"]
