"""Dynamic workflow graph builder for employee runtime."""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from component_library.quality.schemas import Alternative, DecisionPoint, EvidenceSource
from component_library.work.schemas import (
    AnalysisInput,
    ConfidenceInput,
    DraftInput,
    ExecutiveAssistantPlan,
    VerificationInput,
)
from employee_runtime.core.state import EmployeeState
from employee_runtime.shared.observability import get_langfuse_client

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
STATE_KEYS = set(EmployeeState.__annotations__)


def build_graph(spec: dict[str, Any], components: dict[str, Any]) -> StateGraph:
    graph = StateGraph(EmployeeState)
    nodes = {node["node_id"]: node for node in spec["nodes"]}

    for node_id, node in nodes.items():
        graph.add_node(node_id, _node_handler(node, components))

    graph.add_edge(START, spec["entry"])
    grouped_edges: dict[str, list[dict[str, Any]]] = {}
    for edge in spec["edges"]:
        grouped_edges.setdefault(edge["from_node"], []).append(edge)

    for from_node, edges in grouped_edges.items():
        conditional = [edge for edge in edges if edge.get("condition")]
        unconditional = [edge for edge in edges if not edge.get("condition")]
        if conditional:
            route_map = {
                edge["to_node"]: edge["to_node"]
                for edge in conditional + unconditional
            }
            graph.add_conditional_edges(
                from_node,
                _route_factory(conditional, unconditional),
                route_map,
            )
        else:
            for edge in unconditional:
                graph.add_edge(from_node, edge["to_node"])

    for terminal in spec["terminals"]:
        graph.add_edge(terminal, END)
    return graph


def condition_to_callable(cond: str):
    cond = cond.strip()
    if cond.startswith("has_"):
        key = cond.removeprefix("has_")
        return lambda state: bool(_get_value(state, key))
    if " in " in cond:
        field, _, raw_values = cond.partition(" in ")
        values = json.loads(raw_values.replace("'", '"'))
        return lambda state: _get_value(state, field.strip()) in values
    if ">=" in cond:
        field, raw_value = [part.strip() for part in cond.split(">=", 1)]
        value = float(raw_value)
        return lambda state: float(_get_value(state, field) or 0.0) >= value
    if "==" in cond:
        field, raw_value = [part.strip() for part in cond.split("==", 1)]
        value = _parse_literal(raw_value)
        return lambda state: _get_value(state, field) == value
    raise ValueError(f"Unknown condition operator: {cond}")


def load_builtin_workflow_spec(workflow_name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{workflow_name}_spec.json"
    return json.loads(path.read_text())


async def run_streaming(
    spec: dict[str, Any],
    components: dict[str, Any],
    initial_state: EmployeeState,
) -> AsyncGenerator[dict[str, Any], None]:
    state = dict(initial_state)
    nodes = {node["node_id"]: node for node in spec["nodes"]}
    current = spec["entry"]
    visited_guard = 0
    while current:
        visited_guard += 1
        if visited_guard > 50:
            raise RuntimeError("dynamic workflow exceeded step budget")
        yield {"type": "status", "node": current, "status": "started"}
        handler = _node_handler(nodes[current], components)
        delta = await handler(state)
        state = {**state, **delta}
        yield {"type": "status", "node": current, "status": "complete", "state": dict(state)}
        next_node = _next_node(spec, current, state)
        if next_node is None and current in spec["terminals"]:
            break
        current = next_node
    yield {"type": "complete", "state": dict(state)}


def _route_factory(
    conditional_edges: list[dict[str, Any]],
    unconditional_edges: list[dict[str, Any]],
):
    predicates = [(edge["to_node"], condition_to_callable(edge["condition"])) for edge in conditional_edges]
    fallback = unconditional_edges[0]["to_node"] if unconditional_edges else None

    def route(state: dict[str, Any]) -> str:
        for to_node, predicate in predicates:
            if predicate(state):
                return to_node
        if fallback is not None:
            return fallback
        raise ValueError("No workflow edge matched and no fallback edge exists.")

    return route


def _next_node(spec: dict[str, Any], current: str, state: dict[str, Any]) -> str | None:
    edges = [edge for edge in spec["edges"] if edge["from_node"] == current]
    conditional = [edge for edge in edges if edge.get("condition")]
    unconditional = [edge for edge in edges if not edge.get("condition")]
    for edge in conditional:
        if condition_to_callable(edge["condition"])(state):
            return edge["to_node"]
    if unconditional:
        return unconditional[0]["to_node"]
    return None


def _node_handler(node: dict[str, Any], components: dict[str, Any]):
    adapter = node.get("config", {}).get("adapter", "generic_merge")
    component_id = node.get("component_id")
    custom_spec_id = node.get("custom_spec_id")

    async def handler(state: dict[str, Any]) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        with get_langfuse_client().span(
            f"workflow.node.{node['node_id']}",
            input={"task_id": state.get("task_id", ""), "node_id": node["node_id"]},
            metadata={
                "component_id": component_id or "",
                "custom_spec_id": custom_spec_id or "",
                "adapter": adapter,
            },
        ) as span:
            if component_id:
                component = components[component_id]
                result = await _run_component(component, adapter, state, components)
            else:
                result = await _run_custom(custom_spec_id, adapter, state)
            span.end(
                output=result if isinstance(result, dict) else {"result_type": type(result).__name__},
                metadata={"state_keys_before": sorted(state.keys())},
            )
        if not isinstance(result, dict):
            return {}
        merged = _merge_state_update(state, result)
        await _capture_reasoning_record(
            components,
            state,
            merged,
            node_id=node["node_id"],
            component_id=component_id,
            custom_spec_id=custom_spec_id,
            started_at=started_at,
        )
        await _log_node_activity(
            components,
            merged,
            node_id=node["node_id"],
        )
        return {
            key: value
            for key, value in merged.items()
            if state.get(key) != value
        }

    return handler


async def _run_component(
    component: Any,
    adapter: str,
    state: dict[str, Any],
    components: dict[str, Any],
) -> dict[str, Any]:
    if adapter == "sanitize_input":
        result = component.protect(state["raw_input"])
        return {"sanitization_result": result.model_dump()}
    if adapter == "legal_extract":
        result = await component.extract(state["sanitization_result"]["sanitized_input"])
        return {"extracted_data": result.model_dump()}
    if adapter == "legal_analyze":
        result = await component.analyze(AnalysisInput.model_validate({"extraction": state["extracted_data"]}).extraction)
        return {
            "analysis": result.model_dump(),
            "qualification_decision": result.qualification_decision,
            "qualification_reasoning": result.qualification_reasoning,
        }
    if adapter == "legal_confidence":
        result = component.score(
            ConfidenceInput.model_validate({"extraction": state["extracted_data"], "analysis": state["analysis"]})
        )
        return {
            "confidence_report": result.model_dump(),
            "requires_human_approval": result.recommendation != "proceed",
        }
    if adapter == "legal_generate_brief":
        result = await component.generate(
            DraftInput.model_validate(
                {
                    "extraction": state["extracted_data"],
                    "analysis": state["analysis"],
                    "confidence_report": state["confidence_report"],
                }
            )
        )
        verification = components.get("verification_layer")
        verification_result = {}
        if verification is not None:
            verified = verification.verify(VerificationInput(brief=result))
            verification_result = verified.model_dump()
        return {
            "brief": result.model_dump(mode="json"),
            "result_card": result.model_dump(mode="json"),
            "response_summary": result.executive_summary,
            "verification_result": verification_result,
        }
    if adapter == "executive_plan":
        result = component.plan(state["sanitization_result"]["sanitized_input"])
        return {
            "workflow_output": {"plan": result.model_dump(mode="json")},
            "requires_human_approval": result.requires_approval,
            "novel_options": result.novel_options,
            "escalation_reason": result.guidance_request or state.get("escalation_reason", ""),
        }
    if adapter == "executive_schedule":
        result = component.extract_schedule(state["sanitization_result"]["sanitized_input"])
        workflow_output = dict(state.get("workflow_output", {}))
        workflow_output["schedule"] = result.model_dump(mode="json")
        return {"workflow_output": workflow_output}
    if adapter == "executive_draft":
        plan = ExecutiveAssistantPlan.model_validate(state["workflow_output"]["plan"])
        result = component.compose(plan)
        schedule_updates = state.get("workflow_output", {}).get("schedule", {}).get("schedule_updates", [])
        result.schedule_updates = schedule_updates
        return {
            "result_card": {
                "title": result.title,
                "executive_summary": result.summary,
                "drafted_response": result.drafted_response,
                "action_items": result.action_items,
                "finance_actions": result.finance_actions,
                "finance_metrics": plan.finance_metrics,
                "schedule_updates": result.schedule_updates,
                "crm_updates": result.crm_updates,
                "confidence_score": result.confidence_score,
                "novel_options": result.novel_options,
                "recommended_option": result.recommended_option,
                "flags": (
                    ["guidance required"]
                    if result.needs_guidance
                    else ["approval required"] if state.get("requires_human_approval") else []
                ),
            },
            "response_summary": result.summary,
            "novel_options": result.novel_options,
        }
    if adapter == "deliberation_review":
        result = await component.evaluate(
            {
                "proposal_id": state.get("task_id", ""),
                "content": state.get("response_summary", ""),
                "context": state,
                "risk_tier": state.get("input_metadata", {}).get("risk_tier", "medium"),
            }
        )
        return {
            "verification_result": {
                **state.get("verification_result", {}),
                "deliberation": result.model_dump(mode="json"),
            },
            "requires_human_approval": not bool(getattr(result, "approved", False)),
        }

    result = component.execute(state) if hasattr(component, "execute") else state
    if inspect.isawaitable(result):
        result = await result
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return state


async def _run_custom(custom_spec_id: str | None, adapter: str, state: dict[str, Any]) -> dict[str, Any]:
    _ = adapter
    if custom_spec_id is None:
        return state
    if custom_spec_id == "builtin_flag_for_review":
        return {"requires_human_approval": True, "qualification_decision": "needs_review"}
    if custom_spec_id == "builtin_escalate":
        return {
            "qualification_decision": "escalated",
            "requires_human_approval": True,
            "escalation_reason": "Confidence below automatic handling threshold.",
        }
    if custom_spec_id == "builtin_request_approval":
        return {"delivery_status": "awaiting_approval"}
    if custom_spec_id == "builtin_deliver":
        return {"delivery_method": "employee_app", "delivery_status": "delivered"}
    if custom_spec_id == "builtin_log_completion":
        return {"completed_at": datetime.now(UTC).isoformat()}
    module = importlib.import_module(f"generated.{custom_spec_id}")
    if hasattr(module, "execute"):
        result = module.execute(state)
        if inspect.isawaitable(result):
            result = await result
        return result if isinstance(result, dict) else {"workflow_output": result}
    return state


def _get_value(state: dict[str, Any], path: str) -> Any:
    current: Any = state
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            break
    return current


def _parse_literal(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(raw.replace("'", '"'))
    except Exception:
        return raw.strip("\"'")


def _merge_state_update(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    updated = dict(state)
    workflow_output: dict[str, Any] | None = None
    for key, value in result.items():
        if key in STATE_KEYS:
            updated[key] = value
        else:
            if workflow_output is None:
                workflow_output = dict(updated.get("workflow_output", {}))
            workflow_output[key] = value
    if workflow_output is not None:
        updated["workflow_output"] = workflow_output
    return updated


async def _capture_reasoning_record(
    components: dict[str, Any],
    previous_state: dict[str, Any],
    current_state: dict[str, Any],
    *,
    node_id: str,
    component_id: str | None,
    custom_spec_id: str | None,
    started_at: datetime,
) -> None:
    explainability = components.get("explainability")
    if explainability is None:
        return
    task_id = current_state.get("task_id")
    if not task_id:
        return
    confidence = _confidence_for_state(current_state)
    alternatives = _alternatives_for_state(current_state)
    evidence = _evidence_for_state(current_state)
    decision = DecisionPoint(
        task_id=UUID(str(task_id)),
        node_id=node_id,
        decision=_decision_for_state(current_state, node_id),
        rationale=_rationale_for_state(current_state, previous_state, node_id),
        inputs_considered={
            "raw_input": current_state.get("raw_input", ""),
            "input_metadata": current_state.get("input_metadata", {}),
            "sanitization_result": current_state.get("sanitization_result", {}),
            "analysis": current_state.get("analysis", {}),
            "confidence_report": current_state.get("confidence_report", {}),
            "workflow_output": current_state.get("workflow_output", {}),
        },
        alternatives=alternatives,
        evidence=evidence,
        confidence=confidence,
        modules_invoked=[item for item in (component_id, custom_spec_id) if item],
        token_cost=int(current_state.get("input_metadata", {}).get("token_cost", 0) or 0),
        latency_ms=max(0, int((datetime.now(UTC) - started_at).total_seconds() * 1000)),
    )
    record = await explainability.capture(decision)
    current_state.setdefault("workflow_output", {})["last_reasoning_record_id"] = str(record.record_id)


async def _log_node_activity(
    components: dict[str, Any],
    state: dict[str, Any],
    *,
    node_id: str,
) -> None:
    audit = components.get("audit_system")
    if audit is None:
        return
    event_type = "output_produced"
    if node_id in {"flag_for_review", "escalate", "request_approval"}:
        event_type = "approval_requested"
    elif node_id in {"deliver", "log_completion"}:
        event_type = "task_completed"
    details = {
        "node": node_id,
        "decision": _decision_for_state(state, node_id),
        "confidence": _confidence_for_state(state),
    }
    record_id = state.get("workflow_output", {}).get("last_reasoning_record_id")
    if record_id:
        details["record_id"] = record_id
    event = await audit.log_event(
        employee_id=str(state.get("employee_id", "")),
        org_id=str(state.get("org_id", "")),
        event_type=event_type,
        details=details,
    )
    state.setdefault("audit_event_ids", []).append(event.get("id", event.get("hash", "")))


def _decision_for_state(state: dict[str, Any], node_id: str) -> str:
    if node_id in {"analyze_intake", "score_confidence", "flag_for_review", "escalate", "log_completion"}:
        return str(state.get("qualification_decision") or state.get("confidence_report", {}).get("recommendation") or node_id)
    if node_id in {"draft_response", "generate_brief", "deliver"}:
        return str(state.get("response_summary") or state.get("delivery_status") or node_id)
    return node_id


def _rationale_for_state(current_state: dict[str, Any], previous_state: dict[str, Any], node_id: str) -> str:
    for candidate in (
        current_state.get("qualification_reasoning"),
        current_state.get("escalation_reason"),
        current_state.get("response_summary"),
        current_state.get("analysis", {}).get("summary"),
        current_state.get("workflow_output", {}).get("plan", {}).get("rationale"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    if current_state.get("requires_human_approval") and not previous_state.get("requires_human_approval"):
        return f"{node_id} triggered a human approval requirement."
    return f"{node_id} completed without an explicit rationale."


def _confidence_for_state(state: dict[str, Any]) -> float:
    for candidate in (
        state.get("confidence_report", {}).get("overall_score"),
        state.get("result_card", {}).get("confidence_score"),
        state.get("analysis", {}).get("confidence"),
        state.get("brief", {}).get("confidence_score"),
    ):
        if candidate is not None:
            return float(candidate)
    return 0.0


def _alternatives_for_state(state: dict[str, Any]) -> list[Alternative]:
    options = state.get("novel_options") or state.get("result_card", {}).get("novel_options", [])
    recommended = str(
        state.get("result_card", {}).get("recommended_option")
        or state.get("workflow_output", {}).get("plan", {}).get("recommended_option", "")
    )
    alternatives: list[Alternative] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        key = str(option.get("key", option.get("label", "option")))
        score = 1.0 if key == recommended else 0.55
        alternatives.append(
            Alternative(
                option=f"{key}: {option.get('label', key)}",
                score=score,
                why_not_chosen="" if key == recommended else str(option.get("description", "Alternative not selected.")),
            )
        )
    return alternatives


def _evidence_for_state(state: dict[str, Any]) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []
    input_type = str(state.get("input_type", "document"))
    raw_input = str(state.get("raw_input", "")).strip()
    if raw_input:
        evidence.append(
            EvidenceSource(
                source_type="email" if input_type == "email" else "document",
                reference=input_type,
                content_snippet=raw_input[:280],
            )
        )
    for fact in state.get("extracted_data", {}).get("key_facts", [])[:3]:
        evidence.append(
            EvidenceSource(
                source_type="document",
                reference="extracted_fact",
                content_snippet=str(fact)[:280],
            )
        )
    return evidence
