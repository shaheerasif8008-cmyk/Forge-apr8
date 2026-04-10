"""Component selector: maps requirements to library components."""

from __future__ import annotations

from factory.models.blueprint import SelectedComponent
from factory.models.requirements import EmployeeRequirements


async def select_components(requirements: EmployeeRequirements) -> list[SelectedComponent]:
    """Select appropriate library components for the given requirements.

    Args:
        requirements: Structured employee requirements.

    Returns:
        List of SelectedComponent instances from the Component Library.
    """
    # V1: rule-based selection. Future: LLM-assisted selection.
    components: list[SelectedComponent] = []

    # Always include a primary model
    components.append(SelectedComponent(
        category="models",
        component_id="anthropic_provider",
        config={"model": "claude-3-5-sonnet-20241022"},
    ))

    # Map required tools
    tool_map = {
        "email": "email_tool",
        "calendar": "calendar_tool",
        "slack": "messaging_tool",
        "crm": "crm_tool",
        "search": "search_tool",
    }
    for keyword, component_id in tool_map.items():
        if any(keyword in t.lower() for t in requirements.required_tools):
            components.append(SelectedComponent(category="tools", component_id=component_id))

    # Always include core data modules
    for data_module in ("knowledge_base", "operational_memory", "working_memory", "org_context"):
        components.append(SelectedComponent(category="data", component_id=data_module))

    # Quality modules based on risk tier
    from factory.models.requirements import RiskTier
    quality_base = ["confidence_scorer", "autonomy_manager", "audit_system", "input_protection"]
    if requirements.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
        quality_base += ["verification_layer", "adversarial_review", "explainability",
                         "approval_manager", "compliance_rules"]
    for q in quality_base:
        components.append(SelectedComponent(category="quality", component_id=q))

    return components
