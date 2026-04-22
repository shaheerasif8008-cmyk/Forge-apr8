"""Employee blueprint — output of the Architect stage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from factory.models.requirements import EmployeeArchetype


def utc_now() -> datetime:
    return datetime.now(UTC)


class SelectedComponent(BaseModel):
    """A single component selected from the library for this employee."""

    category: str = Field(description="models | work | tools | data | quality")
    component_id: str
    version: str = "latest"
    config: dict[str, object] = Field(default_factory=dict)
    rationale: str = ""


class CustomCodeSpec(BaseModel):
    """Specification for code that must be generated (no library component covers it)."""

    name: str
    description: str
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    node_id: str
    component_id: str | None = None
    custom_spec_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference(self) -> WorkflowNode:
        if bool(self.component_id) == bool(self.custom_spec_id):
            raise ValueError("WorkflowNode must reference exactly one of component_id or custom_spec_id.")
        return self


class WorkflowEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str | None = None


class WorkflowGraphSpec(BaseModel):
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    entry: str
    terminals: list[str]

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowGraphSpec:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("WorkflowGraphSpec node IDs must be unique.")
        node_id_set = set(node_ids)
        if self.entry not in node_id_set:
            raise ValueError("WorkflowGraphSpec entry must reference an existing node.")
        if not self.terminals:
            raise ValueError("WorkflowGraphSpec requires at least one terminal node.")
        if any(terminal not in node_id_set for terminal in self.terminals):
            raise ValueError("WorkflowGraphSpec terminals must reference existing nodes.")

        for edge in self.edges:
            if edge.from_node not in node_id_set or edge.to_node not in node_id_set:
                raise ValueError("WorkflowGraphSpec edge references unknown node.")

        adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_id_set}
        for edge in self.edges:
            adjacency[edge.from_node].add(edge.to_node)

        visited: set[str] = set()
        stack = [self.entry]
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            stack.extend(adjacency[node_id] - visited)
        if visited != node_id_set:
            missing = ", ".join(sorted(node_id_set - visited))
            raise ValueError(f"WorkflowGraphSpec contains disconnected nodes: {missing}")

        terminal_reachable = any(
            self._can_reach_terminal(self.entry, terminal, adjacency, set())
            for terminal in self.terminals
        )
        if not terminal_reachable:
            raise ValueError("WorkflowGraphSpec entry cannot reach a terminal node.")
        return self

    def _can_reach_terminal(
        self,
        current: str,
        target: str,
        adjacency: dict[str, set[str]],
        seen: set[str],
    ) -> bool:
        if current == target:
            return True
        if current in seen:
            return False
        seen = set(seen)
        seen.add(current)
        return any(self._can_reach_terminal(next_node, target, adjacency, seen) for next_node in adjacency[current])


class IdentityLayerInputs(BaseModel):
    core_identity: str = ""
    role_definition: str = ""
    organizational_map: str = ""
    behavioral_rules: str = ""
    retrieved_context: str = ""
    self_awareness: str = ""


class MonitoringPolicy(BaseModel):
    health_check_interval_minutes: int = 15
    drift_detection_enabled: bool = True
    alert_channels: list[str] = Field(default_factory=list)


class DeploymentSpec(BaseModel):
    format: str = "web"
    target: str = "hosted_web"
    hosted_base_url: str = ""


class UIProfile(BaseModel):
    app_title: str = ""
    app_badge: str = ""
    primary_channel_label: str = "Employee App"
    capabilities: list[str] = Field(default_factory=list)


class EmployeeBlueprint(BaseModel):
    """Complete design document for an employee, produced by the Architect."""

    id: UUID = Field(default_factory=uuid4)
    requirements_id: UUID
    org_id: UUID
    employee_type: EmployeeArchetype = EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
    employee_name: str
    components: list[SelectedComponent] = Field(default_factory=list)
    custom_code_specs: list[CustomCodeSpec] = Field(default_factory=list)
    workflow_id: str = "legal_intake"
    workflow_graph: WorkflowGraphSpec | None = None
    tool_permissions: list[str] = Field(default_factory=list)
    identity_layers: IdentityLayerInputs = Field(default_factory=IdentityLayerInputs)
    workflow_description: str = Field("")
    autonomy_profile: dict[str, object] = Field(
        default_factory=dict,
        description="Risk thresholds, approval gates, escalation rules",
    )
    monitoring_policy: MonitoringPolicy = Field(default_factory=MonitoringPolicy)
    deployment_spec: DeploymentSpec = Field(default_factory=DeploymentSpec)
    ui_profile: UIProfile = Field(default_factory=UIProfile)
    estimated_cost_per_task_usd: float | None = None
    architect_reasoning: str = Field("")
    created_at: datetime = Field(default_factory=utc_now)
