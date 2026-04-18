from __future__ import annotations

import pytest

from factory.models.blueprint import CustomCodeSpec, WorkflowGraphSpec
from factory.models.requirements import EmployeeArchetype
from factory.pipeline.architect.component_selector import select_components
from factory.pipeline.architect.workflow_designer import design_workflow


@pytest.mark.anyio
async def test_legal_intake_workflow_contains_expected_nodes(sample_requirements) -> None:
    components = await select_components(sample_requirements)
    gaps = [CustomCodeSpec(name="conflict_checker", description="Run conflict checks", inputs={}, outputs={})]
    graph = await design_workflow(sample_requirements, components, gaps)

    node_ids = {node.node_id for node in graph.nodes}
    assert {"extract_information", "analyze_intake", "score_confidence", "generate_brief"} <= node_ids
    assert "conflict_checker" in node_ids


@pytest.mark.anyio
async def test_executive_assistant_workflow_differs(sample_requirements) -> None:
    sample_requirements.employee_type = EmployeeArchetype.EXECUTIVE_ASSISTANT
    components = await select_components(sample_requirements)
    graph = await design_workflow(sample_requirements, components, [])
    node_ids = {node.node_id for node in graph.nodes}
    assert {"plan_work", "coordinate_schedule", "draft_response"} <= node_ids


def test_workflow_graph_rejects_disconnected_node() -> None:
    with pytest.raises(ValueError):
        WorkflowGraphSpec.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "component_id": "text_processor"},
                    {"node_id": "b", "component_id": "document_analyzer"},
                ],
                "edges": [],
                "entry": "a",
                "terminals": ["b"],
            }
        )


def test_workflow_graph_rejects_missing_reference() -> None:
    with pytest.raises(ValueError):
        WorkflowGraphSpec.model_validate(
            {
                "nodes": [{"node_id": "a"}],
                "edges": [],
                "entry": "a",
                "terminals": ["a"],
            }
        )


def test_workflow_graph_rejects_duplicate_node_ids() -> None:
    with pytest.raises(ValueError):
        WorkflowGraphSpec.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "component_id": "text_processor"},
                    {"node_id": "a", "component_id": "document_analyzer"},
                ],
                "edges": [],
                "entry": "a",
                "terminals": ["a"],
            }
        )
