"""Gap analyzer: identifies what requires custom code generation."""

from __future__ import annotations

from factory.models.blueprint import CustomCodeSpec, SelectedComponent
from factory.models.requirements import EmployeeRequirements


async def identify_gaps(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
) -> list[CustomCodeSpec]:
    """Identify capabilities that have no matching library component.

    Args:
        requirements: Validated requirements document.
        components: Library components already selected.

    Returns:
        List of CustomCodeSpec items the Generator must produce.
    """
    covered_tools = {c.component_id for c in components if c.category == "tools"}
    gaps: list[CustomCodeSpec] = []

    for tool in requirements.required_tools:
        normalized = tool.lower().replace(" ", "_")
        if normalized not in covered_tools:
            gaps.append(CustomCodeSpec(
                name=f"custom_{normalized}_tool",
                description=f"Custom tool integration for: {tool}",
                inputs={"request": "str"},
                outputs={"result": "str"},
            ))

    return gaps
