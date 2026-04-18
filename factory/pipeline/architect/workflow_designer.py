"""Workflow designer: produces a WorkflowGraphSpec from requirements and selected components."""

from __future__ import annotations

import json
from pathlib import Path

from component_library.models.anthropic_provider import AnthropicProvider
from factory.config import get_settings
from factory.models.blueprint import CustomCodeSpec, SelectedComponent, WorkflowGraphSpec
from factory.models.requirements import EmployeeArchetype, EmployeeRequirements

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "workflow_design.md"


async def design_workflow(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
    gaps: list[CustomCodeSpec],
) -> WorkflowGraphSpec:
    settings = get_settings()
    try:
        return await _design_with_llm(requirements, components, gaps)
    except Exception:
        if settings.anthropic_api_key:
            raise
        return _design_fallback(requirements, components, gaps)


async def _design_with_llm(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
    gaps: list[CustomCodeSpec],
) -> WorkflowGraphSpec:
    provider = AnthropicProvider()
    settings = get_settings()
    await provider.initialize(
        {
            "model": settings.generator_model,
            "api_key": settings.anthropic_api_key,
            "max_tokens": 4096,
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
                "gaps": [gap.model_dump(mode="json") for gap in gaps],
            },
            indent=2,
            sort_keys=True,
        )
    )
    content = await provider.complete(
        [{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.0,
        system="Return strict JSON only.",
    )
    return WorkflowGraphSpec.model_validate(json.loads(content))


def _design_fallback(
    requirements: EmployeeRequirements,
    components: list[SelectedComponent],
    gaps: list[CustomCodeSpec],
) -> WorkflowGraphSpec:
    component_ids = {component.component_id for component in components}
    gap_ids = [gap.name for gap in gaps]
    if requirements.employee_type == EmployeeArchetype.EXECUTIVE_ASSISTANT:
        return WorkflowGraphSpec.model_validate(
            {
                "nodes": [
                    {"node_id": "sanitize_input", "component_id": "input_protection", "config": {"adapter": "sanitize_input"}},
                    {"node_id": "plan_work", "component_id": "workflow_executor", "config": {"adapter": "executive_plan"}},
                    {"node_id": "coordinate_schedule", "component_id": "scheduler_manager", "config": {"adapter": "executive_schedule"}},
                    {"node_id": "draft_response", "component_id": "communication_manager", "config": {"adapter": "executive_draft"}},
                    {"node_id": "request_approval", "custom_spec_id": "builtin_request_approval", "config": {"adapter": "builtin_request_approval"}},
                    {"node_id": "deliver", "custom_spec_id": "builtin_deliver", "config": {"adapter": "builtin_deliver"}},
                    {"node_id": "log_completion", "custom_spec_id": "builtin_log_completion", "config": {"adapter": "builtin_log_completion"}},
                ],
                "edges": [
                    {"from_node": "sanitize_input", "to_node": "plan_work"},
                    {"from_node": "plan_work", "to_node": "coordinate_schedule"},
                    {"from_node": "coordinate_schedule", "to_node": "draft_response"},
                    {"from_node": "draft_response", "to_node": "request_approval", "condition": "requires_human_approval == true"},
                    {"from_node": "draft_response", "to_node": "deliver"},
                    {"from_node": "request_approval", "to_node": "deliver"},
                    {"from_node": "deliver", "to_node": "log_completion"},
                ],
                "entry": "sanitize_input",
                "terminals": ["log_completion"],
            }
        )

    nodes = [
        {"node_id": "sanitize_input", "component_id": "input_protection", "config": {"adapter": "sanitize_input"}},
        {"node_id": "extract_information", "component_id": "text_processor", "config": {"adapter": "legal_extract"}},
        {"node_id": "analyze_intake", "component_id": "document_analyzer", "config": {"adapter": "legal_analyze"}},
        {"node_id": "score_confidence", "component_id": "confidence_scorer", "config": {"adapter": "legal_confidence"}},
        {"node_id": "flag_for_review", "custom_spec_id": "builtin_flag_for_review", "config": {"adapter": "builtin_flag_for_review"}},
        {"node_id": "generate_brief", "component_id": "draft_generator", "config": {"adapter": "legal_generate_brief"}},
        {"node_id": "escalate", "custom_spec_id": "builtin_escalate", "config": {"adapter": "builtin_escalate"}},
        {"node_id": "deliver", "custom_spec_id": "builtin_deliver", "config": {"adapter": "builtin_deliver"}},
        {"node_id": "log_completion", "custom_spec_id": "builtin_log_completion", "config": {"adapter": "builtin_log_completion"}},
    ]
    edges = [
        {"from_node": "sanitize_input", "to_node": "extract_information"},
        {"from_node": "extract_information", "to_node": "analyze_intake"},
        {"from_node": "analyze_intake", "to_node": "score_confidence"},
        {"from_node": "score_confidence", "to_node": "generate_brief", "condition": "confidence_report.overall_score >= 0.85"},
        {"from_node": "score_confidence", "to_node": "flag_for_review", "condition": "confidence_report.overall_score >= 0.4"},
        {"from_node": "score_confidence", "to_node": "escalate"},
        {"from_node": "flag_for_review", "to_node": "generate_brief"},
    ]
    if gap_ids:
        nodes.insert(
            3,
            {
                "node_id": "conflict_checker",
                "custom_spec_id": gap_ids[0],
                "config": {"adapter": "generic_merge"},
            },
        )
        edges[2] = {"from_node": "analyze_intake", "to_node": "conflict_checker"}
        edges.insert(3, {"from_node": "conflict_checker", "to_node": "score_confidence"})
    if "adversarial_review" in component_ids:
        nodes.append({"node_id": "deliberate_output", "component_id": "adversarial_review", "config": {"adapter": "deliberation_review"}})
        edges.extend(
            [
                {"from_node": "generate_brief", "to_node": "deliberate_output"},
                {"from_node": "deliberate_output", "to_node": "deliver"},
            ]
        )
    else:
        edges.append({"from_node": "generate_brief", "to_node": "deliver"})
    edges.extend(
        [
            {"from_node": "escalate", "to_node": "deliver"},
            {"from_node": "deliver", "to_node": "log_completion"},
        ]
    )
    return WorkflowGraphSpec.model_validate(
        {
            "nodes": nodes,
            "edges": edges,
            "entry": "sanitize_input",
            "terminals": ["log_completion"],
        }
    )
