from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowPackEvaluationCase(BaseModel):
    case_id: str
    input: str
    expected_lane: str
    required_terms: list[str] = Field(default_factory=list)


class WorkflowPack(BaseModel):
    pack_id: str
    display_name: str
    version: str = "1.0.0"
    description: str
    supported_lanes: list[str]
    classification_hints: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    optional_tools: list[str] = Field(default_factory=list)
    output_templates: dict[str, str] = Field(default_factory=dict)
    autonomy_overrides: dict[str, str] = Field(default_factory=dict)
    domain_vocabulary: list[str] = Field(default_factory=list)
    onboarding_questions: list[str] = Field(default_factory=list)
    evaluation_cases: list[WorkflowPackEvaluationCase] = Field(default_factory=list)
    roi_metrics: dict[str, float] = Field(default_factory=dict)
