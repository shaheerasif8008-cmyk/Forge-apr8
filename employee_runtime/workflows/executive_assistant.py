"""Executive assistant workflow for generalized Forge employees."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from employee_runtime.core.state import EmployeeState

NodeHandler = Callable[[EmployeeState], Awaitable[EmployeeState]]


def _route_for_approval(state: EmployeeState) -> str:
    if state.get("requires_human_approval"):
        return "request_approval"
    return "deliver"


def create_handlers(components: dict[str, Any]) -> dict[str, NodeHandler]:
    audit = components.get("audit_system")
    input_protection = components["input_protection"]
    workflow_executor = components["workflow_executor"]
    scheduler_manager = components["scheduler_manager"]
    communication_manager = components["communication_manager"]

    async def _log(state: EmployeeState, event_type: str, details: dict[str, Any]) -> None:
        if audit is None:
            return
        event = await audit.log_event(
            employee_id=state["employee_id"],
            org_id=state["org_id"],
            event_type=event_type,
            details=details,
        )
        state.setdefault("audit_event_ids", []).append(event.get("id", event.get("hash", "")))

    async def sanitize_input(state: EmployeeState) -> EmployeeState:
        result = input_protection.protect(state["raw_input"])
        state["sanitization_result"] = result.model_dump()
        await _log(state, "task_started", {"node": "sanitize_input", "safe": result.is_safe})
        return state

    async def plan_work(state: EmployeeState) -> EmployeeState:
        plan = workflow_executor.plan(state["sanitization_result"]["sanitized_input"])
        state["workflow_output"] = {"plan": plan.model_dump(mode="json")}
        state["requires_human_approval"] = plan.requires_approval
        await _log(state, "workflow_planned", state["workflow_output"]["plan"])
        return state

    async def coordinate_schedule(state: EmployeeState) -> EmployeeState:
        schedule = scheduler_manager.extract_schedule(state["sanitization_result"]["sanitized_input"])
        state["workflow_output"]["schedule"] = schedule.model_dump(mode="json")
        await _log(state, "schedule_evaluated", state["workflow_output"]["schedule"])
        return state

    async def draft_response(state: EmployeeState) -> EmployeeState:
        plan = workflow_executor.plan(state["sanitization_result"]["sanitized_input"])
        response = communication_manager.compose(plan)
        schedule_updates = state["workflow_output"].get("schedule", {}).get("schedule_updates", [])
        response.schedule_updates = schedule_updates
        state["result_card"] = {
            "title": response.title,
            "executive_summary": response.summary,
            "drafted_response": response.drafted_response,
            "action_items": response.action_items,
            "schedule_updates": response.schedule_updates,
            "confidence_score": response.confidence_score,
            "flags": ["approval required"] if state.get("requires_human_approval") else [],
        }
        state["response_summary"] = response.summary
        await _log(state, "output_produced", {"node": "draft_response", "confidence": response.confidence_score})
        return state

    async def request_approval(state: EmployeeState) -> EmployeeState:
        state["delivery_status"] = "awaiting_approval"
        await _log(state, "approval_requested", {"node": "request_approval"})
        return state

    async def deliver(state: EmployeeState) -> EmployeeState:
        state["delivery_method"] = "employee_app"
        state["delivery_status"] = "delivered"
        await _log(state, "task_completed", {"node": "deliver", "delivery_status": "delivered"})
        return state

    async def log_completion(state: EmployeeState) -> EmployeeState:
        state["completed_at"] = datetime.now(UTC).isoformat()
        await _log(state, "task_completed", {"node": "log_completion", "workflow": "executive_assistant"})
        return state

    return {
        "sanitize_input": sanitize_input,
        "plan_work": plan_work,
        "coordinate_schedule": coordinate_schedule,
        "draft_response": draft_response,
        "request_approval": request_approval,
        "deliver": deliver,
        "log_completion": log_completion,
    }


def build_graph(components: dict[str, Any]) -> StateGraph:
    handlers = create_handlers(components)
    graph = StateGraph(EmployeeState)
    for name, handler in handlers.items():
        graph.add_node(name, handler)

    graph.add_edge(START, "sanitize_input")
    graph.add_edge("sanitize_input", "plan_work")
    graph.add_edge("plan_work", "coordinate_schedule")
    graph.add_edge("coordinate_schedule", "draft_response")
    graph.add_conditional_edges(
        "draft_response",
        _route_for_approval,
        {"request_approval": "request_approval", "deliver": "deliver"},
    )
    graph.add_edge("request_approval", "deliver")
    graph.add_edge("deliver", "log_completion")
    graph.add_edge("log_completion", END)
    return graph


async def run_streaming(
    components: dict[str, Any],
    initial_state: EmployeeState,
) -> AsyncGenerator[dict[str, Any], None]:
    handlers = create_handlers(components)
    state = initial_state
    for node_name in ("sanitize_input", "plan_work", "coordinate_schedule", "draft_response"):
        yield {"type": "status", "node": node_name, "status": "started"}
        state = await handlers[node_name](state)
        yield {"type": "status", "node": node_name, "status": "complete", "state": dict(state)}

    route = _route_for_approval(state)
    if route == "request_approval":
        yield {"type": "status", "node": "request_approval", "status": "started"}
        state = await handlers["request_approval"](state)
        yield {"type": "status", "node": "request_approval", "status": "complete", "state": dict(state)}

    for node_name in ("deliver", "log_completion"):
        yield {"type": "status", "node": node_name, "status": "started"}
        state = await handlers[node_name](state)
        yield {"type": "status", "node": node_name, "status": "complete", "state": dict(state)}

    yield {"type": "complete", "state": dict(state)}
