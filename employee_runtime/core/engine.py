"""LangGraph workflow runner — the employee's execution engine."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from component_library.interfaces import BaseComponent
from employee_runtime.core.state import EmployeeState
from employee_runtime.workflows.dynamic_builder import (
    build_graph,
    load_builtin_workflow_spec,
    run_streaming,
)
from factory.observability.langfuse_client import get_langfuse_client

logger = structlog.get_logger(__name__)


class EmployeeEngine:
    """Runs the LangGraph workflow for a deployed employee.

    The graph is assembled from nodes provided by each selected Work capability
    module. The engine manages state, handles errors, and routes to human
    escalation when confidence falls below threshold.
    """

    def __init__(
        self,
        workflow_name: str,
        components: dict[str, BaseComponent],
        config: dict[str, Any],
    ) -> None:
        self._workflow_name = workflow_name
        self._components = components
        self._config = config
        self._workflow_spec = self._resolve_workflow_spec()
        self._graph = self._build_graph()
        self._app = self._graph.compile()

    def _resolve_workflow_spec(self) -> dict[str, Any]:
        spec = self._config.get("workflow_graph")
        if isinstance(spec, dict) and spec.get("nodes"):
            return spec
        return load_builtin_workflow_spec(self._workflow_name)

    def _build_graph(self):
        return build_graph(self._workflow_spec, self._components)

    def _initial_state(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
        task_id: str = "",
    ) -> EmployeeState:
        return {
            "task_id": task_id or str(uuid4()),
            "employee_id": self._config["employee_id"],
            "org_id": str(self._config["org_id"]),
            "conversation_id": conversation_id,
            "raw_input": task_input,
            "input_type": input_type,
            "input_metadata": metadata or {},
            "sanitization_result": {},
            "extracted_data": {},
            "analysis": {},
            "confidence_report": {},
            "verification_result": {},
            "qualification_decision": "",
            "qualification_reasoning": "",
            "brief": {},
            "result_card": {},
            "response_summary": "",
            "workflow_output": {},
            "novel_options": [],
            "correction_record": {},
            "delivery_method": "",
            "delivery_status": "",
            "errors": [],
            "audit_event_ids": [],
            "requires_human_approval": False,
            "escalation_reason": "",
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": "",
        }

    async def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        logger.info("engine_run_start")
        with get_langfuse_client().trace(
            f"employee_workflow.{self._workflow_name}",
            input=initial_state,
            metadata={"workflow": self._workflow_name},
            user_id=str(initial_state.get("org_id", "")),
            session_id=str(initial_state.get("task_id", "")),
        ) as trace:
            result: dict[str, Any] = await self._app.ainvoke(initial_state)
            trace.end(output=result)
        logger.info("engine_run_complete")
        return result

    async def process_task(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
        task_id: str = "",
    ) -> EmployeeState:
        initial_state = self._initial_state(task_input, input_type, metadata, conversation_id, task_id)
        with get_langfuse_client().trace(
            f"employee_workflow.{self._workflow_name}",
            input=initial_state,
            metadata={"workflow": self._workflow_name},
            user_id=str(initial_state.get("org_id", "")),
            session_id=str(initial_state.get("task_id", "")),
        ) as trace:
            result = await self._app.ainvoke(initial_state)
            trace.end(output=result)
        return result

    async def process_task_streaming(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
        task_id: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        initial_state = self._initial_state(task_input, input_type, metadata, conversation_id, task_id)
        with get_langfuse_client().trace(
            f"employee_workflow.{self._workflow_name}.stream",
            input=initial_state,
            metadata={"workflow": self._workflow_name, "streaming": True},
            user_id=str(initial_state.get("org_id", "")),
            session_id=str(initial_state.get("task_id", "")),
        ) as trace:
            final_state: dict[str, Any] | None = None
            async for event in run_streaming(
                self._workflow_spec,
                self._components,
                initial_state,
            ):
                if event.get("type") == "complete":
                    final_state = dict(event.get("state", {}))
                yield event
            trace.end(output=final_state or {})
