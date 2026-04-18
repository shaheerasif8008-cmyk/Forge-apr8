from __future__ import annotations

import pytest

from component_library.interfaces import ComponentHealth, WorkCapability
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
