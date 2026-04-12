"""Conversational Analyst helpers for requirements intake."""

from __future__ import annotations

from dataclasses import dataclass, field

from factory.models.requirements import EmployeeArchetype, RiskTier


@dataclass
class AnalystSession:
    session_id: str
    org_id: str = ""
    raw_messages: list[dict[str, str]] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    inferred_employee_type: EmployeeArchetype = EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE
    suggested_risk_tier: RiskTier = RiskTier.MEDIUM


def start_session(session_id: str, initial_prompt: str, org_id: str = "") -> AnalystSession:
    session = AnalystSession(session_id=session_id, org_id=org_id)
    session.raw_messages.append({"role": "user", "content": initial_prompt})
    session.inferred_employee_type = infer_employee_type(initial_prompt)
    session.suggested_risk_tier = infer_risk_tier(initial_prompt)
    session.clarifying_questions = build_clarifying_questions(initial_prompt, session.inferred_employee_type)
    return session


def append_message(session: AnalystSession, role: str, content: str) -> AnalystSession:
    session.raw_messages.append({"role": role, "content": content})
    if role == "user":
        session.clarifying_questions = build_clarifying_questions(content, session.inferred_employee_type)
    return session


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


def build_clarifying_questions(prompt: str, employee_type: EmployeeArchetype) -> list[str]:
    questions = [
        "Who supervises this employee and through which primary communication channel?",
        "Which external systems must the employee use autonomously?",
    ]
    lowered = prompt.lower()
    if employee_type == EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE:
        questions.append("What practice areas, conflict rules, and qualification criteria should the employee follow?")
    else:
        questions.append("What calendar, messaging, CRM, and follow-up responsibilities should the employee own?")
    if "approval" not in lowered:
        questions.append("Which actions require explicit human approval?")
    return questions[:4]
