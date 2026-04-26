from __future__ import annotations

from factory.models.blueprint import WorkflowEdge, WorkflowGraphSpec, WorkflowNode
from factory.models.orm import BlueprintRow
from factory.persistence import blueprint_to_row_payload


def test_blueprint_row_payload_omits_non_persisted_workflow_graph(sample_blueprint) -> None:
    blueprint = sample_blueprint.model_copy(
        update={
            "workflow_graph": WorkflowGraphSpec(
                nodes=[
                    WorkflowNode(node_id="extract", component_id="text_processor"),
                    WorkflowNode(node_id="brief", component_id="draft_generator"),
                ],
                edges=[WorkflowEdge(from_node="extract", to_node="brief")],
                entry="extract",
                terminals=["brief"],
            )
        }
    )

    payload = blueprint_to_row_payload(blueprint)

    assert "workflow_graph" not in payload
    BlueprintRow(**payload)
