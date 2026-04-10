"""Architect designer: maps requirements to a concrete EmployeeBlueprint."""

from __future__ import annotations

import structlog

from factory.models.blueprint import EmployeeBlueprint
from factory.models.requirements import EmployeeRequirements
from factory.pipeline.architect.component_selector import select_components
from factory.pipeline.architect.gap_analyzer import identify_gaps
from factory.pipeline.architect.blueprint_builder import assemble_blueprint

logger = structlog.get_logger(__name__)


async def design_employee(requirements: EmployeeRequirements) -> EmployeeBlueprint:
    """Produce an EmployeeBlueprint from validated requirements.

    Args:
        requirements: Validated EmployeeRequirements from the Analyst stage.

    Returns:
        EmployeeBlueprint ready for the Builder.
    """
    logger.info("architect_designing", employee=requirements.name, org=str(requirements.org_id))
    components = await select_components(requirements)
    gaps = await identify_gaps(requirements, components)
    blueprint = await assemble_blueprint(requirements, components, gaps)
    logger.info("architect_blueprint_ready", blueprint_id=str(blueprint.id))
    return blueprint
