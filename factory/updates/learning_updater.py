"""Type 2: Incremental learning — continuous, pausable."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LearningUpdateState(BaseModel):
    enabled: bool = True
    cadence: str = "continuous"
    paused: bool = False
    paused_until: datetime | None = None
    pause_reason: str | None = None
