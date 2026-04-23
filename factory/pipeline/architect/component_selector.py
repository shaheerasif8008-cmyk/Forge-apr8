"""Component selector: maps requirements to library components."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from component_library.models.anthropic_provider import AnthropicProvider
from component_library.registry import describe_all_components
from component_library.status import is_component_production_ready
from factory.config import get_settings
from factory.models.blueprint import SelectedComponent
from factory.models.requirements import EmployeeArchetype, EmployeeRequirements

LEGAL_BASELINE_COMPONENTS: tuple[tuple[str, str, dict[str, object]], ...] = (
    (
        "models",
        "litellm_router",
        {
            "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
            "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
        },
    ),
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

EXECUTIVE_ASSISTANT_COMPONENTS: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("models", "anthropic_provider", {"model": "claude-3-5-sonnet-20241022"}),
    ("work", "workflow_executor", {}),
    ("work", "communication_manager", {}),
    ("work", "scheduler_manager", {}),
    ("work", "draft_generator", {}),
    ("tools", "email_tool", {}),
    ("tools", "calendar_tool", {}),
    ("tools", "messaging_tool", {}),
    ("tools", "crm_tool", {}),
    ("data", "operational_memory", {}),
    ("data", "working_memory", {}),
    ("data", "context_assembler", {}),
    ("data", "org_context", {}),
    ("quality", "confidence_scorer", {}),
    ("quality", "audit_system", {}),
    ("quality", "input_protection", {}),
    ("quality", "verification_layer", {}),
    ("quality", "autonomy_manager", {}),
)

TOOL_MAP: dict[str, str] = {
    "email": "email_tool",
    "calendar": "calendar_tool",
    "slack": "messaging_tool",
    "teams": "messaging_tool",
    "crm": "crm_tool",
    "search": "search_tool",
}
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "component_selection.md"
logger = structlog.get_logger(__name__)


class ArchitectError(RuntimeError):
    pass


async def select_components(requirements: EmployeeRequirements) -> list[SelectedComponent]:
    """Select appropriate library components for the given requirements.

    Args:
        requirements: Structured employee requirements.

    Returns:
        List of SelectedComponent instances from the Component Library.
    """
    settings = get_settings()
    if settings.use_llm_architect:
        try:
            return await _select_components_with_llm(requirements)
        except ArchitectError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "architect_llm_selector_fallback",
                reason=str(exc),
                fallback="rule_based_component_selector",
            )
    return _select_components_with_fallback(requirements)


def _select_components_with_fallback(requirements: EmployeeRequirements) -> list[SelectedComponent]:
    baseline = (
        EXECUTIVE_ASSISTANT_COMPONENTS
        if requirements.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT
        else LEGAL_BASELINE_COMPONENTS
    )
    components: list[SelectedComponent] = [
        SelectedComponent(category=category, component_id=component_id, config=config)
        for category, component_id, config in baseline
        if is_component_production_ready(component_id)
    ]

    known_component_ids = {component.component_id for component in components}
    for tool_name in requirements.required_tools:
        normalized = tool_name.lower()
        for keyword, component_id in TOOL_MAP.items():
            if keyword in normalized and component_id not in known_component_ids:
                if is_component_production_ready(component_id):
                    components.append(SelectedComponent(category="tools", component_id=component_id))
                known_component_ids.add(component_id)

    # Quality modules based on risk tier
    from factory.models.requirements import RiskTier

    quality_base = {"autonomy_manager", "explainability"}
    if requirements.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
        quality_base |= {"adversarial_review", "explainability", "approval_manager", "compliance_rules"}
    for q in quality_base:
        if q not in known_component_ids and is_component_production_ready(q):
            components.append(SelectedComponent(category="quality", component_id=q))
            known_component_ids.add(q)

    _validate_selected_components(requirements, components)
    return components


async def _select_components_with_llm(requirements: EmployeeRequirements) -> list[SelectedComponent]:
    catalog = [description.model_dump(mode="json") for description in describe_all_components()]
    prompt = PROMPT_PATH.read_text()
    payload = (
        f"{prompt}\n\n"
        f"EmployeeRequirements:\n{json.dumps(requirements.model_dump(mode='json'), indent=2, sort_keys=True)}\n\n"
        f"Component catalog:\n{json.dumps(catalog, indent=2, sort_keys=True)}\n"
    )
    components = await _call_selector_llm(payload)
    _validate_selected_components(requirements, components, allow_unknown_tools=False)
    return components


async def _call_selector_llm(prompt: str) -> list[SelectedComponent]:
    settings = get_settings()
    provider = AnthropicProvider()
    await provider.initialize(
        {
            "model": settings.generator_model,
            "api_key": settings.anthropic_api_key,
            "max_tokens": 4096,
            "temperature": 0.0,
        }
    )
    content = await provider.complete(
        [{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.0,
        system="Return strict JSON only.",
    )
    payload = json.loads(content)
    return [SelectedComponent.model_validate(item) for item in payload]


def _validate_selected_components(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
    *,
    allow_unknown_tools: bool = True,
) -> None:
    component_ids = {component.component_id for component in components}
    for tool_name in requirements.required_tools:
        matched = False
        keyword_match_found = False
        lowered = tool_name.lower()
        for keyword, component_id in TOOL_MAP.items():
            if keyword in lowered:
                keyword_match_found = True
                if component_id in component_ids:
                    matched = True
                    break
        if matched:
            continue
        if keyword_match_found:
            raise ArchitectError(f"Unsatisfied tool requirement: {tool_name}")
        if not allow_unknown_tools and lowered:
            raise ArchitectError(f"Unsatisfied tool requirement: {tool_name}")

    if requirements.employee_type == EmployeeArchetype.LEGAL_INTAKE_ASSOCIATE:
        required = {"text_processor", "document_analyzer", "draft_generator"}
        missing = required - component_ids
        if missing:
            raise ArchitectError(f"Missing legal intake components: {', '.join(sorted(missing))}")
    if requirements.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT:
        required = {"workflow_executor", "communication_manager", "scheduler_manager"}
        missing = required - component_ids
        if missing:
            raise ArchitectError(f"Missing executive assistant components: {', '.join(sorted(missing))}")
