"""Type 2: Incremental learning — continuous, pausable."""

from __future__ import annotations

from pydantic import BaseModel


class LearningUpdateState(BaseModel):
    enabled: bool = True
    cadence: str = "continuous"
