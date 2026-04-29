from __future__ import annotations

from pydantic import BaseModel, Field

from employee_runtime.workflow_packs.base import WorkflowPack

KNOWLEDGE_TERMS = {
    "prepare",
    "draft",
    "summarize",
    "analyze",
    "brief",
    "memo",
    "report",
    "research",
    "recommend",
    "compare",
    "explain",
    "investor",
    "client-ready",
    "client update",
    "follow-up",
}
PROCESS_TERMS = {
    "route",
    "notify",
    "schedule",
    "create",
    "mark",
    "reconcile",
    "checklist",
    "crm",
    "calendar",
    "send",
    "approve",
    "approval",
    "owner",
    "record",
}
RISKY_ACTIONS = {
    "external_send",
    "post_journal_entry",
    "case_acceptance",
    "legal_advice",
    "file_tax_return",
}


class TaskClassification(BaseModel):
    lane: str
    confidence: float
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str


class KernelTaskPlan(BaseModel):
    lane: str
    steps: list[str]
    required_tools: list[str] = Field(default_factory=list)
    expected_deliverables: list[str] = Field(default_factory=list)
    approval_points: list[str] = Field(default_factory=list)
    output_template: str = ""
    completion_criteria: list[str] = Field(default_factory=list)
    pack_ids: list[str] = Field(default_factory=list)


def classify_task(task_input: str, packs: list[WorkflowPack]) -> TaskClassification:
    lowered = task_input.lower()
    knowledge_matches = sorted(term for term in KNOWLEDGE_TERMS if term in lowered)
    process_matches = sorted(term for term in PROCESS_TERMS if term in lowered)

    for pack in packs:
        for hint in pack.classification_hints:
            if hint.lower() not in lowered:
                continue
            if "business_process" in pack.supported_lanes:
                process_matches.append(hint)
            if "knowledge_work" in pack.supported_lanes:
                knowledge_matches.append(hint)

    if knowledge_matches and process_matches:
        lane = "hybrid"
    elif process_matches:
        lane = "business_process"
    else:
        lane = "knowledge_work"

    confidence = 0.55 + min(0.4, 0.08 * len(set(knowledge_matches + process_matches)))
    return TaskClassification(
        lane=lane,
        confidence=round(confidence, 2),
        matched_terms=sorted(set(knowledge_matches + process_matches)),
        rationale=f"Classified as {lane} from matched task and workflow-pack terms.",
    )


def create_task_plan(
    *,
    task_input: str,
    classification: TaskClassification,
    packs: list[WorkflowPack],
) -> KernelTaskPlan:
    _ = task_input
    lane = classification.lane
    steps = ["Understand requested outcome", "Gather available context"]
    if lane in {"knowledge_work", "hybrid"}:
        steps.extend(["Analyze inputs and assumptions", "Compose professional deliverable"])
    if lane in {"business_process", "hybrid"}:
        steps.extend(["Validate required fields", "Execute allowed system actions through ToolBroker"])
    steps.append("Deliver professional output")

    required_tools: list[str] = []
    approval_points = ["external_send"]
    output_template = ""
    for pack in packs:
        required_tools.extend(pack.required_tools)
        output_template = output_template or pack.output_templates.get(lane) or pack.output_templates.get("hybrid", "")
        approval_points.extend(action for action, mode in pack.autonomy_overrides.items() if mode != "autonomous")

    if classification.confidence < 0.7:
        approval_points.append("low_confidence_clarification")

    return KernelTaskPlan(
        lane=lane,
        steps=list(dict.fromkeys(steps)),
        required_tools=list(dict.fromkeys(required_tools)),
        expected_deliverables=[
            "brief_card",
            "action_log" if lane in {"business_process", "hybrid"} else "written_deliverable",
        ],
        approval_points=sorted(set(approval_points) & (RISKY_ACTIONS | {"low_confidence_clarification"})),
        output_template=output_template or "Professional task brief with summary, evidence, actions, and next steps.",
        completion_criteria=["output_created", "audit_recorded", "roi_recorded"],
        pack_ids=[pack.pack_id for pack in packs],
    )


def task_plan_to_context(plan: KernelTaskPlan) -> dict[str, object]:
    return {
        "kernel": {
            "task_lane": plan.lane,
            "plan": plan.model_dump(mode="json"),
        }
    }


def estimate_roi(
    packs: list[WorkflowPack],
    *,
    completed_tasks: int,
    escalations: int,
    rework_events: int,
) -> dict[str, float | int]:
    minutes_per_task = max([pack.roi_metrics.get("default_minutes_saved", 20.0) for pack in packs] or [20.0])
    return {
        "completed_tasks": completed_tasks,
        "escalations": escalations,
        "rework_events": rework_events,
        "estimated_minutes_saved": max(0.0, round(completed_tasks * minutes_per_task, 2)),
    }
