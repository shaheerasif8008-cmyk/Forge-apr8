"""Deployment and DeploymentStatus models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DeploymentFormat(str, Enum):
    WEB = "web"
    DESKTOP = "desktop"
    SERVER = "server"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    CONNECTING = "connecting"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    INACTIVE = "inactive"


class Deployment(BaseModel):
    """A live deployment of a built employee package."""

    id: UUID = Field(default_factory=uuid4)
    build_id: UUID
    org_id: UUID
    format: DeploymentFormat = DeploymentFormat.WEB
    status: DeploymentStatus = DeploymentStatus.PENDING
    access_url: str = ""
    infrastructure: dict[str, object] = Field(default_factory=dict)
    health_last_checked: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: datetime | None = None
