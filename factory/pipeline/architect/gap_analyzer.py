"""Gap analyzer: identifies what requires custom code generation."""

from __future__ import annotations

import json
from pathlib import Path

from component_library.models.anthropic_provider import AnthropicProvider
from factory.models.blueprint import CustomCodeSpec, SelectedComponent
from factory.models.requirements import EmployeeRequirements
from factory.config import get_settings
from factory.pipeline.architect.component_selector import TOOL_MAP

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "gap_analysis.md"


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
    settings = get_settings()
    try:
        return await _identify_gaps_with_llm(requirements, components)
    except Exception:
        if settings.anthropic_api_key:
            raise
        return _identify_gaps_fallback(requirements, components)


async def _identify_gaps_with_llm(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
) -> list[CustomCodeSpec]:
    provider = AnthropicProvider()
    settings = get_settings()
    await provider.initialize(
        {
            "model": settings.generator_model,
            "api_key": settings.anthropic_api_key,
            "max_tokens": 2048,
            "temperature": 0.0,
        }
    )
    prompt = (
        PROMPT_PATH.read_text()
        + "\n\n"
        + json.dumps(
            {
                "requirements": requirements.model_dump(mode="json"),
                "components": [component.model_dump(mode="json") for component in components],
            },
            indent=2,
            sort_keys=True,
        )
    )
    content = await provider.complete(
        [{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.0,
        system="Return strict JSON only.",
    )
    return [CustomCodeSpec.model_validate(item) for item in json.loads(content)]


def _identify_gaps_fallback(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
) -> list[CustomCodeSpec]:
    covered_tools = {c.component_id for c in components if c.category == "tools"}
    gaps: list[CustomCodeSpec] = []
    for tool in requirements.required_tools:
        normalized = tool.lower().replace(" ", "_")
        matched_component = None
        for keyword, component_id in TOOL_MAP.items():
            if keyword in tool.lower():
                matched_component = component_id
                break
        if matched_component is not None and matched_component in covered_tools:
            continue
        if matched_component is None or matched_component not in covered_tools:
            gaps.append(
                CustomCodeSpec(
                    name=f"custom_{normalized}_tool",
                    description=f"Custom tool integration for: {tool}",
                    inputs={"request": "str"},
                    outputs={"result": "str"},
                )
            )
    return gaps
