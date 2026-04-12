"""Type 1: Security updates — automatic, rollbackable, max 30-day delay."""

from __future__ import annotations

from pydantic import BaseModel


class SecurityUpdate(BaseModel):
    update_id: str
    title: str
    severity: str
    auto_apply: bool = True
    rollbackable: bool = True


DEFAULT_SECURITY_UPDATES = [
    SecurityUpdate(
        update_id="sec-001",
        title="Base image refresh",
        severity="high",
    )
]
