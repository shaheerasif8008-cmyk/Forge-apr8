"""Type 1: Security updates — automatic, rollbackable, max 30-day delay."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SecurityUpdate(BaseModel):
    update_id: str
    title: str
    severity: str
    auto_apply: bool = True
    rollbackable: bool = True


class SecurityUpdateState(SecurityUpdate):
    status: Literal["available", "applied", "delayed", "rolled_back"] = "available"
    applied_at: datetime | None = None
    delayed_until: datetime | None = None
    delay_reason: str | None = None
    rolled_back_at: datetime | None = None


DEFAULT_SECURITY_UPDATES = [
    SecurityUpdate(
        update_id="sec-001",
        title="Base image refresh",
        severity="high",
    )
]
