"""LangGraph workflow runner — the employee's execution engine."""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import StateGraph

logger = structlog.get_logger(__name__)


class EmployeeEngine:
    """Runs the LangGraph workflow for a deployed employee.

    The graph is assembled from nodes provided by each selected Work capability
    module. The engine manages state, handles errors, and routes to human
    escalation when confidence falls below threshold.
    """

    def __init__(self, workflow: StateGraph, config: dict[str, Any]) -> None:
        self._workflow = workflow
        self._config = config
        self._app = workflow.compile()

    async def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the workflow from an initial state.

        Args:
            initial_state: Starting state dict for the LangGraph run.

        Returns:
            Final state after workflow completion.
        """
        logger.info("engine_run_start")
        result: dict[str, Any] = await self._app.ainvoke(initial_state)
        logger.info("engine_run_complete")
        return result
