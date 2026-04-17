from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import component_library.data.context_assembler  # noqa: F401
import component_library.data.operational_memory  # noqa: F401
import component_library.data.org_context  # noqa: F401
import component_library.data.working_memory  # noqa: F401
import component_library.models.litellm_router  # noqa: F401
import component_library.quality.audit_system  # noqa: F401
import component_library.quality.confidence_scorer  # noqa: F401
import component_library.quality.input_protection  # noqa: F401
import component_library.quality.verification_layer  # noqa: F401
import component_library.tools.email_tool  # noqa: F401
import component_library.work.document_analyzer  # noqa: F401
import component_library.work.draft_generator  # noqa: F401
import component_library.work.text_processor  # noqa: F401
from component_library.component_factory import create_components
from component_library.work.schemas import (
    DocumentAnalyzerOutput,
    IntakeBrief,
    LegalIntakeExtraction,
)
from employee_runtime.core.engine import EmployeeEngine
from tests.fixtures.sample_emails import (
    AMBIGUOUS,
    CLEAR_QUALIFIED,
    CLEAR_UNQUALIFIED,
    POTENTIAL_CONFLICT,
    URGENT,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("email_text", "expected_decision"),
    [
        (CLEAR_QUALIFIED, "qualified"),
        (CLEAR_UNQUALIFIED, "not_qualified"),
        (AMBIGUOUS, "needs_review"),
        (POTENTIAL_CONFLICT, "qualified"),
        (URGENT, "qualified"),
    ],
)
async def test_legal_intake_workflow(email_text: str, expected_decision: str) -> None:
    components = await create_components(
        [
            "litellm_router",
            "text_processor",
            "document_analyzer",
            "draft_generator",
            "operational_memory",
            "working_memory",
            "context_assembler",
            "org_context",
            "confidence_scorer",
            "audit_system",
            "input_protection",
            "verification_layer",
            "email_tool",
        ],
        {
            "litellm_router": {
                "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
                "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
            },
            "document_analyzer": {"practice_areas": ["personal injury", "employment", "commercial dispute"]},
            "draft_generator": {"default_attorney": "Arthur Review"},
            "operational_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "working_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "context_assembler": {"system_identity": "Arthur", "operational_memory": None},
            "org_context": {"people": [], "escalation_chain": []},
            "confidence_scorer": {},
            "audit_system": {},
            "input_protection": {},
            "verification_layer": {},
            "email_tool": {},
        },
    )
    components["context_assembler"]._operational_memory = components["operational_memory"]
    engine = EmployeeEngine("legal_intake", components, {"employee_id": "employee-1", "org_id": "org-1"})
    result = await engine.process_task(email_text)
    assert result["qualification_decision"] == expected_decision
    assert "task_completed" in [event["event_type"] for event in await components["audit_system"].get_trail("employee-1")]


@pytest.mark.anyio
async def test_legal_intake_workflow_uses_router_backed_components() -> None:
    components = await create_components(
        [
            "litellm_router",
            "text_processor",
            "document_analyzer",
            "draft_generator",
            "operational_memory",
            "working_memory",
            "context_assembler",
            "org_context",
            "confidence_scorer",
            "audit_system",
            "input_protection",
            "verification_layer",
            "email_tool",
        ],
        {
            "litellm_router": {
                "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
                "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
            },
            "text_processor": {"force_llm": True},
            "document_analyzer": {
                "practice_areas": ["personal injury", "employment", "commercial dispute"],
                "force_llm": True,
            },
            "draft_generator": {"default_attorney": "Arthur Review", "force_llm": True},
            "operational_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "working_memory": {"org_id": "org-1", "employee_id": "employee-1"},
            "context_assembler": {"system_identity": "Arthur", "operational_memory": None},
            "org_context": {"people": [], "escalation_chain": []},
            "confidence_scorer": {},
            "audit_system": {},
            "input_protection": {},
            "verification_layer": {},
            "email_tool": {},
        },
    )
    components["context_assembler"]._operational_memory = components["operational_memory"]
    extraction = LegalIntakeExtraction(
        client_name="Sarah Johnson",
        client_email="sarah.johnson@email.com",
        client_phone="(555) 123-4567",
        matter_type="personal injury",
        date_of_incident="February 15, 2026",
        opposing_party="James Miller",
        key_facts=["Client reports a red-light collision with medical treatment and lost work."],
        urgency="high",
        potential_conflicts=["James Miller"],
        estimated_value="$45,000",
        referral_source="google",
        raw_summary="Sarah Johnson appears to be seeking help with a personal injury matter.",
        extraction_confidence=0.91,
    )
    analysis = DocumentAnalyzerOutput(
        summary="This inquiry appears to be a qualified matter for the firm.",
        key_findings=["Matter fits the firm's practice profile."],
        risk_flags=[],
        recommended_actions=["Schedule consultation.", "Run formal conflict check."],
        qualification_decision="qualified",
        qualification_reasoning="The matter is within practice scope and includes enough detail to proceed.",
        confidence=0.93,
    )
    brief = IntakeBrief(
        client_info=extraction,
        analysis=analysis,
        confidence_score=0.94,
        executive_summary="Sarah Johnson submitted a qualified personal injury inquiry.",
        recommended_attorney="Arthur Review",
        recommended_practice_area="personal injury",
        next_steps=["Schedule consultation.", "Request supporting records."],
        flags=[],
    )
    components["litellm_router"].complete_structured = AsyncMock(side_effect=[extraction, analysis, brief])

    engine = EmployeeEngine("legal_intake", components, {"employee_id": "employee-1", "org_id": "org-1"})
    result = await engine.process_task(CLEAR_QUALIFIED)

    assert result["qualification_decision"] == "qualified"
    assert result["brief"]["executive_summary"] == "Sarah Johnson submitted a qualified personal injury inquiry."
    assert components["litellm_router"].complete_structured.await_count == 3
