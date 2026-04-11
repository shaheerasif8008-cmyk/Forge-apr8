"""Build, BuildLog, and BuildArtifact models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BuildStatus(str, Enum):
    QUEUED = "queued"
    ASSEMBLING = "assembling"
    GENERATING = "generating"
    PACKAGING = "packaging"
    EVALUATING = "evaluating"
    PASSED = "passed"
    FAILED = "failed"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"


class BuildLog(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    stage: str
    level: str = "info"
    message: str
    detail: dict[str, object] = Field(default_factory=dict)


class BuildArtifact(BaseModel):
    artifact_type: str = Field(description="container_image | config_bundle | test_report")
    location: str = Field(description="S3 URI or container registry tag")
    checksum: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Build(BaseModel):
    """A single build run for an employee."""

    id: UUID = Field(default_factory=uuid4)
    requirements_id: UUID | None = None
    blueprint_id: UUID | None = None
    org_id: UUID
    status: BuildStatus = BuildStatus.QUEUED
    iteration: int = Field(1, description="Generator retry iteration (max 5)")
    logs: list[BuildLog] = Field(default_factory=list)
    artifacts: list[BuildArtifact] = Field(default_factory=list)
    test_report: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
