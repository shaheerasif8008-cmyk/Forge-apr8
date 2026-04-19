"""Canonical package manifest shared by builder, runtime, and deployer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from factory.models.blueprint import DeploymentSpec, MonitoringPolicy, SelectedComponent, UIProfile
from factory.models.requirements import EmployeeArchetype


class IdentityLayers(BaseModel):
    layer_1_core_identity: str
    layer_2_role_definition: str
    layer_3_organizational_map: str
    layer_4_behavioral_rules: str
    layer_5_retrieved_context: str = ""
    layer_6_self_awareness: str


class ArtifactManifest(BaseModel):
    config_path: str = "config.yaml"
    entrypoint: str = "run.py"
    build_dir: str = ""
    generated_files: list[str] = Field(default_factory=list)
    runtime_template: str = ""


class PackageManifest(BaseModel):
    employee_id: UUID
    org_id: UUID
    employee_name: str
    role_title: str = ""
    employee_type: EmployeeArchetype
    workflow: str
    identity_layers: IdentityLayers
    components: list[SelectedComponent] = Field(default_factory=list)
    tool_permissions: list[str] = Field(default_factory=list)
    autonomy_policy: dict[str, object] = Field(default_factory=dict)
    monitoring: MonitoringPolicy = Field(default_factory=MonitoringPolicy)
    updates: dict[str, object] = Field(default_factory=dict)
    deployment: DeploymentSpec = Field(default_factory=DeploymentSpec)
    ui: UIProfile = Field(default_factory=UIProfile)
    communication_channels: list[str] = Field(default_factory=list)
    org_map: list[dict[str, object]] = Field(default_factory=list)
    authority_matrix: dict[str, str] = Field(default_factory=dict)
    artifact_manifest: ArtifactManifest = Field(default_factory=ArtifactManifest)
    created_at: datetime = Field(default_factory=datetime.utcnow)
