"""LangGraph workflow runner — the employee's execution engine."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from langgraph.graph import StateGraph

from component_library.interfaces import BaseComponent
from employee_runtime.core.state import EmployeeState

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
        self._graph = self._build_graph(workflow_name)
        self._app = self._graph.compile()

    def _build_graph(self, name: str) -> StateGraph:
        registry = {
            "legal_intake": ("employee_runtime.workflows.legal_intake", "build_graph"),
            "executive_assistant": ("employee_runtime.workflows.executive_assistant", "build_graph"),
        }
        if name not in registry:
            raise ValueError(f"Unknown workflow: {name}")
        module_name, attr = registry[name]
        module = __import__(module_name, fromlist=[attr])
        return getattr(module, attr)(self._components)

    def _initial_state(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> EmployeeState:
        return {
            "task_id": str(uuid4()),
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
        result: dict[str, Any] = await self._app.ainvoke(initial_state)
        logger.info("engine_run_complete")
        return result

    async def process_task(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> EmployeeState:
        return await self._app.ainvoke(
            self._initial_state(task_input, input_type, metadata, conversation_id)
        )

    async def process_task_streaming(
        self,
        task_input: str,
        input_type: str = "email",
        metadata: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        module_name = {
            "legal_intake": "employee_runtime.workflows.legal_intake",
            "executive_assistant": "employee_runtime.workflows.executive_assistant",
        }.get(self._workflow_name)
        if module_name is None:
            raise ValueError(f"Streaming not implemented for workflow: {self._workflow_name}")
        module = __import__(module_name, fromlist=["run_streaming"])

        async for event in module.run_streaming(
            self._components,
            self._initial_state(task_input, input_type, metadata, conversation_id),
        ):
            yield event
