"""Requirements builder: structures raw client intake into EmployeeRequirements."""

from __future__ import annotations

import structlog

from factory.models.requirements import (
    AuthorityLevel,
    CommunicationRule,
    EmployeeArchetype,
    EmployeeRequirements,
    MonitoringPreferences,
    OrgContact,
    OrgRelationship,
    UpdatePreferences,
)
from factory.pipeline.analyst.conversation import infer_employee_type, infer_risk_tier

logger = structlog.get_logger(__name__)


async def build_requirements(raw_intake: str, org_id: str) -> EmployeeRequirements:
    """Parse raw intake text into a structured EmployeeRequirements document.

    Args:
        raw_intake: Free-form client description of the employee they need.
        org_id: UUID of the client organisation placing the commission.

    Returns:
        Validated EmployeeRequirements ready for the Architect.

    Note:
        V1 accepts structured input directly. V1.5 will use a conversational
        Analyst AI to extract requirements from free-form conversation.
    """
    import uuid

    logger.info("building_requirements", org_id=org_id, intake_length=len(raw_intake))

    inferred_type = infer_employee_type(raw_intake)
    inferred_tools = _infer_tools(raw_intake, inferred_type)
    role_title = (
        "Executive Assistant"
        if inferred_type == EmployeeArchetype.EXECUTIVE_ASSISTANT
        else "Legal Intake Associate"
    )
    return EmployeeRequirements(
        org_id=uuid.UUID(org_id),
        employee_type=inferred_type,
        name="Unnamed Employee" if inferred_type == EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE else "Operations Assistant",
        role_title=role_title,
        role_summary=raw_intake[:500],
        primary_responsibilities=_infer_responsibilities(inferred_type),
        required_tools=inferred_tools,
        communication_channels=["email", "app"],
        risk_tier=infer_risk_tier(raw_intake),
        org_map=[
            OrgContact(
                name="Assigned Supervisor",
                role="Supervisor",
                relationship=OrgRelationship.SUPERVISOR,
            )
        ],
        authority_matrix={
            "send_external_message": AuthorityLevel.REQUIRES_APPROVAL,
            "update_internal_records": AuthorityLevel.AUTONOMOUS,
        },
        communication_rules=[
            CommunicationRule(
                name="business-hours",
                description="Keep non-urgent outreach within normal business hours.",
                channel="email",
            )
        ],
        monitoring_preferences=MonitoringPreferences(),
        update_preferences=UpdatePreferences(),
        raw_intake=raw_intake,
    )


def _infer_tools(raw_intake: str, employee_type: EmployeeArchetype) -> list[str]:
    lowered = raw_intake.lower()
    tools: list[str] = ["email"]
    if employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT or "calendar" in lowered:
        tools.append("calendar")
    if any(keyword in lowered for keyword in ("slack", "teams", "message")):
        tools.append("slack")
    if any(keyword in lowered for keyword in ("crm", "client record", "salesforce", "hubspot")):
        tools.append("crm")
    return list(dict.fromkeys(tools))


def _infer_responsibilities(employee_type: EmployeeArchetype) -> list[str]:
    if employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT:
        return [
            "triage requests",
            "draft executive communications",
            "coordinate scheduling and follow-up",
            "update operational systems",
        ]
    return [
        "process client intake",
        "qualify matters",
        "prepare structured briefs",
        "route work for review",
    ]
