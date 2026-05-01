"""Type 3: Skill module upgrades — optional, client previews and installs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ModuleUpgrade(BaseModel):
    upgrade_id: str = Field(default_factory=lambda: str(uuid4()))
    component_id: str
    target_version: str
    summary: str
    status: Literal["scheduled", "previewed", "installed", "declined"] = "scheduled"
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previewed_at: datetime | None = None
    installed_at: datetime | None = None
    declined_at: datetime | None = None
    decline_reason: str | None = None
