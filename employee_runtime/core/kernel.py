from __future__ import annotations

from typing import Any

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


class KernelExecutionResult(BaseModel):
    lane_handler: str
    assembled_context: str
    context_source: str
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    deliverables: list[dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False


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


class GeneralEmployeeKernel:
    """Runtime kernel that turns workflow-pack contracts into executable work.

    The kernel is intentionally deterministic at the baseline layer. Workflow
    packs define lane hints, tool requirements, templates, and approval modes;
    this runtime class reads those pack contracts, assembles context, and runs
    the appropriate lane handler before workflow-specific modules add deeper
    specialization.
    """

    def __init__(
        self,
        *,
        employee_id: str,
        org_id: str,
        packs: list[WorkflowPack],
        components: dict[str, Any],
        tool_broker: Any | None = None,
    ) -> None:
        self._employee_id = employee_id
        self._org_id = org_id
        self._packs = packs
        self._components = components
        self._tool_broker = tool_broker

    async def execute_task(
        self,
        task_input: str,
        *,
        input_type: str,
        request_context: dict[str, Any],
        conversation_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        classification = classify_task(task_input, self._packs)
        plan = create_task_plan(
            task_input=task_input,
            classification=classification,
            packs=self._packs,
        )
        assembled_context, context_source = await self._assemble_context(
            task_input,
            request_context=request_context,
            conversation_id=conversation_id,
        )
        if plan.lane == "knowledge_work":
            execution = await self._run_knowledge_work(
                task_input,
                plan=plan,
                assembled_context=assembled_context,
                context_source=context_source,
            )
        elif plan.lane == "business_process":
            execution = await self._run_business_process(
                task_input,
                plan=plan,
                assembled_context=assembled_context,
                context_source=context_source,
            )
        else:
            execution = await self._run_hybrid_work(
                task_input,
                plan=plan,
                assembled_context=assembled_context,
                context_source=context_source,
            )

        card = self._result_card(
            task_input,
            plan=plan,
            classification=classification,
            execution=execution,
        )
        kernel_payload = {
            **task_plan_to_context(plan)["kernel"],
            "classification": classification.model_dump(mode="json"),
            "execution": execution.model_dump(mode="json"),
            "input_type": input_type,
            "task_id": task_id,
        }
        return {
            "workflow_output": {"kernel": kernel_payload},
            "result_card": card,
            "brief": card,
            "response_summary": str(card["executive_summary"]),
            "requires_human_approval": execution.approval_required,
        }

    async def _assemble_context(
        self,
        task_input: str,
        *,
        request_context: dict[str, Any],
        conversation_id: str,
    ) -> tuple[str, str]:
        assembler = self._components.get("context_assembler")
        if assembler is not None and hasattr(assembler, "assemble"):
            context = await assembler.assemble(
                task_input,
                self._employee_id,
                self._org_id,
                conversation_id,
                int(request_context.get("token_budget", 8000) or 8000),
            )
            return str(context), "context_assembler"
        return f"TASK INPUT\n{task_input}", "kernel_minimal_context"

    async def _run_knowledge_work(
        self,
        task_input: str,
        *,
        plan: KernelTaskPlan,
        assembled_context: str,
        context_source: str,
    ) -> KernelExecutionResult:
        return KernelExecutionResult(
            lane_handler="knowledge_work",
            assembled_context=assembled_context,
            context_source=context_source,
            deliverables=[
                {
                    "type": "professional_brief",
                    "title": "Knowledge work brief",
                    "body": self._compose_brief(task_input, plan, assembled_context),
                }
            ],
            approval_required="low_confidence_clarification" in plan.approval_points,
        )

    async def _run_business_process(
        self,
        task_input: str,
        *,
        plan: KernelTaskPlan,
        assembled_context: str,
        context_source: str,
    ) -> KernelExecutionResult:
        tool_results = await self._run_reversible_tool_steps(task_input, plan)
        return KernelExecutionResult(
            lane_handler="business_process",
            assembled_context=assembled_context,
            context_source=context_source,
            tool_results=tool_results,
            deliverables=[
                {
                    "type": "process_status",
                    "title": "Business process execution record",
                    "body": self._compose_process_record(task_input, plan, tool_results),
                }
            ],
            approval_required=bool(plan.approval_points),
        )

    async def _run_hybrid_work(
        self,
        task_input: str,
        *,
        plan: KernelTaskPlan,
        assembled_context: str,
        context_source: str,
    ) -> KernelExecutionResult:
        knowledge = await self._run_knowledge_work(
            task_input,
            plan=plan,
            assembled_context=assembled_context,
            context_source=context_source,
        )
        process = await self._run_business_process(
            task_input,
            plan=plan,
            assembled_context=assembled_context,
            context_source=context_source,
        )
        return KernelExecutionResult(
            lane_handler="hybrid",
            assembled_context=assembled_context,
            context_source=context_source,
            tool_results=process.tool_results,
            deliverables=[*knowledge.deliverables, *process.deliverables],
            approval_required=knowledge.approval_required or process.approval_required,
        )

    async def _run_reversible_tool_steps(self, task_input: str, plan: KernelTaskPlan) -> list[dict[str, Any]]:
        if self._tool_broker is None:
            return []
        results: list[dict[str, Any]] = []
        for tool_id in plan.required_tools:
            action, params = self._safe_tool_action(tool_id, task_input)
            if not action:
                continue
            try:
                result = await self._tool_broker.execute(
                    tool_id,
                    action,
                    **params,
                    org_id=self._org_id,
                    confidence=0.9,
                )
                results.append(
                    {
                        "tool_id": tool_id,
                        "action": action,
                        "success": bool(getattr(result, "success", True)),
                        "data": dict(getattr(result, "data", {}) or {}),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "tool_id": tool_id,
                        "action": action,
                        "success": False,
                        "error": str(exc),
                    }
                )
        return results

    def _safe_tool_action(self, tool_id: str, task_input: str) -> tuple[str, dict[str, Any]]:
        if tool_id == "email_tool":
            return "check_inbox", {"criteria": task_input[:80]}
        if tool_id == "messaging_tool":
            return "history", {}
        if tool_id == "calendar_tool":
            return "list_events", {}
        if tool_id == "crm_tool":
            return "lookup_contact", {"name": self._first_named_token(task_input)}
        if tool_id == "custom_api_tool":
            return "get", {"path": "/health"}
        return "provider_status", {}

    def _result_card(
        self,
        task_input: str,
        *,
        plan: KernelTaskPlan,
        classification: TaskClassification,
        execution: KernelExecutionResult,
    ) -> dict[str, Any]:
        return {
            "executive_summary": self._summary(task_input, plan, execution),
            "lane": plan.lane,
            "confidence": classification.confidence,
            "sections": execution.deliverables,
            "actions": [
                {
                    "tool_id": item.get("tool_id"),
                    "action": item.get("action"),
                    "success": item.get("success"),
                }
                for item in execution.tool_results
            ],
            "approval_points": list(plan.approval_points),
            "completion_criteria": list(plan.completion_criteria),
        }

    def _summary(self, task_input: str, plan: KernelTaskPlan, execution: KernelExecutionResult) -> str:
        approval_note = " Approval is required before risky external action." if execution.approval_required else ""
        return f"{plan.lane.replace('_', ' ').title()} handled: {task_input.strip()[:180]}.{approval_note}"

    def _compose_brief(self, task_input: str, plan: KernelTaskPlan, assembled_context: str) -> str:
        context_excerpt = " ".join(assembled_context.split())[:320]
        return (
            f"Request: {task_input.strip()}\n"
            f"Template: {plan.output_template}\n"
            f"Context used: {context_excerpt}"
        )

    def _compose_process_record(
        self,
        task_input: str,
        plan: KernelTaskPlan,
        tool_results: list[dict[str, Any]],
    ) -> str:
        successful = [item for item in tool_results if item.get("success")]
        return (
            f"Request: {task_input.strip()}\n"
            f"Steps: {', '.join(plan.steps)}\n"
            f"Reversible tool checks completed: {len(successful)}/{len(tool_results)}"
        )

    def _first_named_token(self, task_input: str) -> str:
        for token in task_input.replace(".", " ").replace(",", " ").split():
            if token[:1].isupper() and len(token) > 2:
                return token
        return "unknown"


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
