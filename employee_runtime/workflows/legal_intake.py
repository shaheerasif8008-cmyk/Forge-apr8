"""Legal intake workflow for the Phase 1 employee runtime."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from component_library.work.schemas import (
    AnalysisInput,
    ConfidenceInput,
    DraftInput,
    VerificationInput,
)
from employee_runtime.core.state import EmployeeState

NodeHandler = Callable[[EmployeeState], Awaitable[EmployeeState]]


def route_by_confidence(state: EmployeeState) -> str:
    score = state["confidence_report"]["overall_score"]
    if score >= 0.85:
        return "generate_brief"
    if score >= 0.4:
        return "flag_for_review"
    return "escalate"


def create_handlers(components: dict[str, Any]) -> dict[str, NodeHandler]:
    audit = components.get("audit_system")
    input_protection = components["input_protection"]
    text_processor = components["text_processor"]
    document_analyzer = components["document_analyzer"]
    confidence_scorer = components["confidence_scorer"]
    draft_generator = components["draft_generator"]
    verification_layer = components["verification_layer"]

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

    async def extract_information(state: EmployeeState) -> EmployeeState:
        extraction = await text_processor.extract(state["sanitization_result"]["sanitized_input"])
        state["extracted_data"] = extraction.model_dump()
        await _log(state, "llm_called", {"node": "extract_information", "confidence": extraction.extraction_confidence})
        return state

    async def analyze_intake(state: EmployeeState) -> EmployeeState:
        analysis = await document_analyzer.analyze(
            AnalysisInput(**{"extraction": state["extracted_data"]}).extraction
        )
        state["analysis"] = analysis.model_dump()
        state["qualification_decision"] = analysis.qualification_decision
        state["qualification_reasoning"] = analysis.qualification_reasoning
        await _log(state, "output_produced", {"node": "analyze_intake", "decision": analysis.qualification_decision, "confidence": analysis.confidence})
        return state

    async def score_confidence(state: EmployeeState) -> EmployeeState:
        confidence_report = confidence_scorer.score(
            ConfidenceInput.model_validate(
                {"extraction": state["extracted_data"], "analysis": state["analysis"]}
            )
        )
        state["confidence_report"] = confidence_report.model_dump()
        state["requires_human_approval"] = confidence_report.recommendation != "proceed"
        await _log(state, "output_produced", {"node": "score_confidence", "confidence": confidence_report.overall_score})
        return state

    async def flag_for_review(state: EmployeeState) -> EmployeeState:
        state["requires_human_approval"] = True
        state["qualification_decision"] = "needs_review"
        await _log(state, "approval_requested", {"node": "flag_for_review"})
        return state

    async def generate_brief(state: EmployeeState) -> EmployeeState:
        brief = await draft_generator.generate(
            DraftInput.model_validate(
                {
                    "extraction": state["extracted_data"],
                    "analysis": state["analysis"],
                    "confidence_report": state["confidence_report"],
                }
            )
        )
        verification = verification_layer.verify(VerificationInput(brief=brief))
        state["brief"] = brief.model_dump(mode="json")
        state["result_card"] = state["brief"]
        state["response_summary"] = brief.executive_summary
        state["verification_result"] = verification.model_dump()
        await _log(state, "output_produced", {"node": "generate_brief", "valid": verification.is_valid})
        return state

    async def escalate(state: EmployeeState) -> EmployeeState:
        state["qualification_decision"] = "escalated"
        state["requires_human_approval"] = True
        state["escalation_reason"] = "Confidence below automatic handling threshold."
        await _log(state, "approval_requested", {"node": "escalate", "reason": state["escalation_reason"]})
        return state

    async def deliver(state: EmployeeState) -> EmployeeState:
        state["delivery_method"] = "employee_app"
        state["delivery_status"] = "delivered"
        await _log(state, "task_completed", {"node": "deliver", "delivery_status": "delivered"})
        return state

    async def log_completion(state: EmployeeState) -> EmployeeState:
        state["completed_at"] = datetime.now(UTC).isoformat()
        await _log(state, "task_completed", {"node": "log_completion", "decision": state.get("qualification_decision", "")})
        return state

    return {
        "sanitize_input": sanitize_input,
        "extract_information": extract_information,
        "analyze_intake": analyze_intake,
        "score_confidence": score_confidence,
        "flag_for_review": flag_for_review,
        "generate_brief": generate_brief,
        "escalate": escalate,
        "deliver": deliver,
        "log_completion": log_completion,
    }


def build_graph(components: dict[str, Any]) -> StateGraph:
    handlers = create_handlers(components)
    graph = StateGraph(EmployeeState)
    for name, handler in handlers.items():
        graph.add_node(name, handler)

    graph.add_edge(START, "sanitize_input")
    graph.add_edge("sanitize_input", "extract_information")
    graph.add_edge("extract_information", "analyze_intake")
    graph.add_edge("analyze_intake", "score_confidence")
    graph.add_conditional_edges(
        "score_confidence",
        route_by_confidence,
        {
            "generate_brief": "generate_brief",
            "flag_for_review": "flag_for_review",
            "escalate": "escalate",
        },
    )
    graph.add_edge("flag_for_review", "generate_brief")
    graph.add_edge("generate_brief", "deliver")
    graph.add_edge("escalate", "deliver")
    graph.add_edge("deliver", "log_completion")
    graph.add_edge("log_completion", END)
    return graph


async def run_streaming(
    components: dict[str, Any],
    initial_state: EmployeeState,
) -> AsyncGenerator[dict[str, Any], None]:
    handlers = create_handlers(components)
    state = initial_state
    ordered_nodes = [
        "sanitize_input",
        "extract_information",
        "analyze_intake",
        "score_confidence",
    ]
    for node_name in ordered_nodes:
        yield {"type": "status", "node": node_name, "status": "started"}
        state = await handlers[node_name](state)
        yield {"type": "status", "node": node_name, "status": "complete", "state": dict(state)}

    route = route_by_confidence(state)
    if route == "flag_for_review":
        for node_name in ("flag_for_review", "generate_brief"):
            yield {"type": "status", "node": node_name, "status": "started"}
            state = await handlers[node_name](state)
            yield {"type": "status", "node": node_name, "status": "complete", "state": dict(state)}
    elif route == "generate_brief":
        yield {"type": "status", "node": "generate_brief", "status": "started"}
        state = await handlers["generate_brief"](state)
        yield {"type": "status", "node": "generate_brief", "status": "complete", "state": dict(state)}
    else:
        yield {"type": "status", "node": "escalate", "status": "started"}
        state = await handlers["escalate"](state)
        yield {"type": "status", "node": "escalate", "status": "complete", "state": dict(state)}

    for node_name in ("deliver", "log_completion"):
        yield {"type": "status", "node": node_name, "status": "started"}
        state = await handlers[node_name](state)
        yield {"type": "status", "node": node_name, "status": "complete", "state": dict(state)}
    yield {"type": "complete", "state": dict(state)}
