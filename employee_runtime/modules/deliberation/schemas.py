from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    proposal_id: str
    content: str
    context: dict[str, Any] = Field(default_factory=dict)
    risk_tier: str = "medium"


class Argument(BaseModel):
    role: Literal["advocate", "challenger"]
    model: str
    reasoning: str
    key_points: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    approved: bool
    confidence: float
    majority_concerns: list[str] = Field(default_factory=list)
    dissenting_views: list[str] = Field(default_factory=list)
    reasoning: str


class SupervisorReport(BaseModel):
    rerun_needed: bool
    reason: str = ""
    issues: list[str] = Field(default_factory=list)


class CouncilConfig(BaseModel):
    advocate_models: list[str] = Field(default_factory=lambda: ["openrouter/anthropic/claude-3.5-sonnet", "openrouter/openai/gpt-4o"])
    challenger_models: list[str] = Field(default_factory=lambda: ["openrouter/openai/gpt-4o", "openrouter/anthropic/claude-3.5-haiku"])
    adjudicator_model: str = "openrouter/anthropic/claude-3.5-sonnet"
    supervisor_model: str = "openrouter/anthropic/claude-3.5-haiku"
    max_reruns: int = 3
    max_time_seconds: int = 600
    enable_reruns: bool = True
    trigger_conditions: list[str] = Field(default_factory=list)
