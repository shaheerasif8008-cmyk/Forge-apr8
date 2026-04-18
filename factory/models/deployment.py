"""Deployment and DeploymentStatus models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DeploymentFormat(str, Enum):
    WEB = "web"
    DESKTOP = "desktop"
    SERVER = "server"
    LOCAL = "local"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    CONNECTING = "connecting"
    ACTIVATING = "activating"
    ACTIVE = "active"
    PENDING_CLIENT_ACTION = "pending_client_action"
    DEGRADED = "degraded"
    INACTIVE = "inactive"
    ROLLED_BACK = "rolled_back"


class IntegrationStatus(BaseModel):
    tool_id: str
    provider: str
    composio_connection_id: str | None = None
    oauth_url: str | None = None
    status: Literal["pending", "connected", "failed"] = "pending"


class Deployment(BaseModel):
    """A live deployment of a built employee package."""

    id: UUID = Field(default_factory=uuid4)
    build_id: UUID
    org_id: UUID
    format: DeploymentFormat = DeploymentFormat.WEB
    status: DeploymentStatus = DeploymentStatus.PENDING
    access_url: str = ""
    infrastructure: dict[str, object] = Field(default_factory=dict)
    integrations: list[IntegrationStatus] = Field(default_factory=list)
    health_last_checked: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: datetime | None = None
