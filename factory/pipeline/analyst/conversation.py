"""LLM-driven Analyst conversation graph for requirements intake."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from component_library.models.anthropic_provider import AnthropicProvider
from factory.config import get_settings
from factory.models.requirements import EmployeeArchetype, RiskTier
from factory.pipeline.analyst.domain_knowledge import executive_assistant, legal

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class IntentClassification(BaseModel):
    employee_type: EmployeeArchetype
    risk_tier: RiskTier
    summary: str


class RequirementsExtraction(BaseModel):
    role_summary: str = ""
    primary_responsibilities: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    communication_channels: list[str] = Field(default_factory=list)
    supervisor_email: str = ""
    name: str = ""
    role_title: str = ""
    org_contacts: list[dict[str, str]] = Field(default_factory=list)
    authority_rules: list[str] = Field(default_factory=list)


class QuestionOutput(BaseModel):
    question: str


class CompletenessAssessment(BaseModel):
    score: float
    gap: str = ""


class AnalystGraphState(BaseModel):
    session_id: str
    org_id: str
    messages: list[dict[str, str]] = Field(default_factory=list)
    partial_requirements: dict[str, Any] = Field(default_factory=dict)
    completeness_score: float = 0.0
    next_question: str = ""
    is_complete: bool = False
    timed_out: bool = False
    turn_count: int = 0
    inferred_employee_type: EmployeeArchetype = EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
    suggested_risk_tier: RiskTier = RiskTier.MEDIUM


@dataclass
class AnalystSession:
    session_id: str
    org_id: str = ""
    state: AnalystGraphState | None = None
    completed_requirements_id: str = ""
    requirements_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def raw_messages(self) -> list[dict[str, str]]:
        return list(self.state.messages if self.state else [])

    @property
    def clarifying_questions(self) -> list[str]:
        if self.state is None or not self.state.next_question:
            return []
        return [self.state.next_question]

    @property
    def inferred_employee_type(self) -> EmployeeArchetype:
        if self.state is None:
            return EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
        return self.state.inferred_employee_type

    @property
    def suggested_risk_tier(self) -> RiskTier:
        if self.state is None:
            return RiskTier.MEDIUM
        return self.state.suggested_risk_tier


async def start_session(session_id: str, initial_prompt: str, org_id: str = "") -> AnalystSession:
    initial_state = AnalystGraphState(
        session_id=session_id,
        org_id=org_id,
        messages=[{"role": "user", "content": initial_prompt}],
        turn_count=1,
    )
    state = await _run_graph(initial_state)
    return AnalystSession(session_id=session_id, org_id=org_id, state=state)


async def append_message(session: AnalystSession, role: str, content: str) -> AnalystSession:
    if session.state is None:
        raise RuntimeError("Analyst session has not been initialized.")
    session.state.messages.append({"role": role, "content": content})
    if role == "user" and not session.state.is_complete:
        session.state.turn_count += 1
        session.state = await _run_graph(session.state)
    return session


async def _run_graph(state: AnalystGraphState) -> AnalystGraphState:
    graph = StateGraph(dict)
    graph.add_node("intent_classifier", _intent_classifier_node)
    graph.add_node("domain_router", _domain_router_node)
    graph.add_node("requirements_extractor", _requirements_extractor_node)
    graph.add_node("completeness_checker", _completeness_checker_node)
    graph.add_node("question_generator", _question_generator_node)
    graph.add_node("complete", _complete_node)

    graph.add_edge(START, "intent_classifier")
    graph.add_edge("intent_classifier", "domain_router")
    graph.add_edge("domain_router", "requirements_extractor")
    graph.add_edge("requirements_extractor", "completeness_checker")
    graph.add_conditional_edges(
        "completeness_checker",
        _route_after_completeness,
        {"complete": "complete", "question_generator": "question_generator"},
    )
    graph.add_edge("question_generator", END)
    graph.add_edge("complete", END)
    app = graph.compile()
    updated = await app.ainvoke(state.model_dump(mode="python"))
    return AnalystGraphState.model_validate(updated)


def _route_after_completeness(state: dict[str, Any]) -> str:
    if bool(state.get("is_complete")):
        return "complete"
    return "question_generator"


async def _intent_classifier_node(state: dict[str, Any]) -> dict[str, Any]:
    classification = await _call_structured_llm(
        IntentClassification,
        prompt_name="intent_classifier.md",
        payload={"messages": state.get("messages", [])},
    )
    state["inferred_employee_type"] = classification.employee_type
    state["suggested_risk_tier"] = classification.risk_tier
    partial = dict(state.get("partial_requirements", {}))
    partial.setdefault("role_summary", classification.summary)
    state["partial_requirements"] = partial
    return state


async def _domain_router_node(state: dict[str, Any]) -> dict[str, Any]:
    domain = state.get("inferred_employee_type", EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE)
    state["domain_context"] = _domain_context(domain)
    return state


async def _requirements_extractor_node(state: dict[str, Any]) -> dict[str, Any]:
    extraction = await _call_structured_llm(
        RequirementsExtraction,
        prompt_name="system_prompt.md",
        payload={
            "messages": state.get("messages", []),
            "domain_context": state.get("domain_context", {}),
            "existing": state.get("partial_requirements", {}),
        },
    )
    merged = dict(state.get("partial_requirements", {}))
    for key, value in extraction.model_dump(mode="python").items():
        if isinstance(value, list):
            merged[key] = value or merged.get(key, [])
        elif value:
            merged[key] = value
    state["partial_requirements"] = merged
    return state


async def _completeness_checker_node(state: dict[str, Any]) -> dict[str, Any]:
    if int(state.get("turn_count", 0)) >= 10:
        state["completeness_score"] = 0.0
        state["next_question"] = "This intake timed out before enough detail was gathered."
        state["is_complete"] = False
        state["timed_out"] = True
        return state

    assessment = await _call_structured_llm(
        CompletenessAssessment,
        prompt_name="completeness_checker.md",
        payload={
            "partial_requirements": state.get("partial_requirements", {}),
            "domain_context": state.get("domain_context", {}),
        },
    )
    score = max(0.0, min(float(assessment.score), 1.0))
    state["completeness_score"] = score
    state["missing_gap"] = assessment.gap
    state["is_complete"] = score >= 0.85
    return state


async def _question_generator_node(state: dict[str, Any]) -> dict[str, Any]:
    question = await _call_structured_llm(
        QuestionOutput,
        prompt_name="question_generator.md",
        payload={
            "partial_requirements": state.get("partial_requirements", {}),
            "domain_context": state.get("domain_context", {}),
            "missing_gap": state.get("missing_gap", ""),
        },
    )
    state["next_question"] = question.question
    return state


async def _complete_node(state: dict[str, Any]) -> dict[str, Any]:
    state["next_question"] = ""
    return state


async def _call_structured_llm(
    response_model: type[BaseModel],
    *,
    prompt_name: str,
    payload: dict[str, Any],
) -> BaseModel:
    provider = AnthropicProvider()
    settings = get_settings()
    await provider.initialize(
        {
            "model": settings.generator_model,
            "api_key": settings.anthropic_api_key,
            "max_tokens": 2048,
            "temperature": 0.0,
        }
    )
    prompt = (PROMPTS_DIR / prompt_name).read_text()
    return await provider.structure(
        response_model,
        [{"role": "user", "content": f"{prompt}\n\n{json.dumps(payload, indent=2, default=str)}"}],
        max_tokens=2048,
        temperature=0.0,
    )


def _domain_context(employee_type: EmployeeArchetype) -> dict[str, Any]:
    if employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT:
        return {
            "required_fields": executive_assistant.REQUIRED_FIELDS,
            "example_workflows": executive_assistant.EXAMPLE_WORKFLOWS,
            "compliance_concerns": executive_assistant.COMPLIANCE_CONCERNS,
        }
    return {
        "required_fields": legal.REQUIRED_FIELDS,
        "example_workflows": legal.EXAMPLE_WORKFLOWS,
        "compliance_concerns": legal.COMPLIANCE_CONCERNS,
    }


def infer_employee_type(prompt: str) -> EmployeeArchetype:
    lowered = prompt.lower()
    if any(keyword in lowered for keyword in ("calendar", "meeting", "executive", "follow-up", "inbox")):
        return EmployeeArchetype.EXECUTIVE_ASSISTANT
    return EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE


def infer_risk_tier(prompt: str) -> RiskTier:
    lowered = prompt.lower()
    if any(keyword in lowered for keyword in ("wire transfer", "financial approval", "legal advice", "medical")):
        return RiskTier.HIGH
    if "contract" in lowered or "client intake" in lowered:
        return RiskTier.MEDIUM
    return RiskTier.LOW
