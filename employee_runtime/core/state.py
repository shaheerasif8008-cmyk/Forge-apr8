"""Shared state model for employee LangGraph workflows."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class EmployeeState(BaseModel):
    """State passed between nodes in the employee workflow graph."""

    task_id: str = ""
    input: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    requires_human_approval: bool = False
    escalation_reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
