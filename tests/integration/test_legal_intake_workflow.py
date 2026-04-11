from __future__ import annotations

import pytest

import component_library.data.context_assembler  # noqa: F401
import component_library.data.operational_memory  # noqa: F401
import component_library.data.org_context  # noqa: F401
import component_library.data.working_memory  # noqa: F401
import component_library.quality.audit_system  # noqa: F401
import component_library.quality.confidence_scorer  # noqa: F401
import component_library.quality.input_protection  # noqa: F401
import component_library.quality.verification_layer  # noqa: F401
import component_library.tools.email_tool  # noqa: F401
import component_library.work.document_analyzer  # noqa: F401
import component_library.work.draft_generator  # noqa: F401
import component_library.work.text_processor  # noqa: F401
from component_library.component_factory import create_components
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
