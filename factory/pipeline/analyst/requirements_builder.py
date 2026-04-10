"""Requirements builder: structures raw client intake into EmployeeRequirements."""

from __future__ import annotations

import structlog

from factory.models.requirements import EmployeeRequirements

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

    # V1: pass-through — requirements already structured by the intake form.
    # Future: LLM extraction via Instructor goes here.
    return EmployeeRequirements(
        org_id=uuid.UUID(org_id),
        name="Unnamed Employee",
        role_summary=raw_intake[:500],
        raw_intake=raw_intake,
    )
