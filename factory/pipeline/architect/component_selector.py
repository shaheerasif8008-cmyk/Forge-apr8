"""Component selector: maps requirements to library components."""

from __future__ import annotations

from factory.models.blueprint import SelectedComponent
from factory.models.requirements import EmployeeRequirements


BASELINE_COMPONENTS: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("models", "anthropic_provider", {"model": "claude-3-5-sonnet-20241022"}),
    ("work", "text_processor", {}),
    ("work", "document_analyzer", {}),
    ("work", "draft_generator", {}),
    ("tools", "email_tool", {}),
    ("data", "operational_memory", {}),
    ("data", "working_memory", {}),
    ("data", "context_assembler", {}),
    ("data", "org_context", {}),
    ("quality", "confidence_scorer", {}),
    ("quality", "audit_system", {}),
    ("quality", "input_protection", {}),
    ("quality", "verification_layer", {}),
)

TOOL_MAP: dict[str, str] = {
    "email": "email_tool",
    "calendar": "calendar_tool",
    "slack": "messaging_tool",
    "teams": "messaging_tool",
    "crm": "crm_tool",
    "search": "search_tool",
}


async def select_components(requirements: EmployeeRequirements) -> list[SelectedComponent]:
    """Select appropriate library components for the given requirements.

    Args:
        requirements: Structured employee requirements.

    Returns:
        List of SelectedComponent instances from the Component Library.
    """
    # V1: rule-based selection centered on the current legal_intake runtime.
    components: list[SelectedComponent] = [
        SelectedComponent(category=category, component_id=component_id, config=config)
        for category, component_id, config in BASELINE_COMPONENTS
    ]

    known_component_ids = {component.component_id for component in components}
    for tool_name in requirements.required_tools:
        normalized = tool_name.lower()
        for keyword, component_id in TOOL_MAP.items():
            if keyword in normalized and component_id not in known_component_ids:
                components.append(SelectedComponent(category="tools", component_id=component_id))
                known_component_ids.add(component_id)

    # Quality modules based on risk tier
    from factory.models.requirements import RiskTier

    quality_base = {"autonomy_manager"}
    if requirements.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
        quality_base |= {"adversarial_review", "explainability", "approval_manager", "compliance_rules"}
    for q in quality_base:
        if q not in known_component_ids:
            components.append(SelectedComponent(category="quality", component_id=q))
            known_component_ids.add(q)

    return components
