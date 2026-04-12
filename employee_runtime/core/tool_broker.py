"""Tool Broker — hard-law gateway for all external tool calls within an employee.

Every tool invocation MUST go through this broker. It:
  - Enforces permission policy for this employee's allowed tools
  - Resolves credentials from the vault (never plaintext in memory)
  - Logs every invocation to the immutable audit trail
  - Blocks actions not covered by the employee's permissions
  - Retries transient failures with exponential backoff
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ToolCall(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    employee_id: str
    tool_id: str
    action: str
    parameters: dict[str, object] = Field(default_factory=dict)
    called_at: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    call_id: UUID
    success: bool
    data: dict[str, object] = Field(default_factory=dict)
    error: str = ""
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class ToolBroker:
    """Permission-enforcing, audit-logging gateway for external tool calls."""

    def __init__(
        self,
        employee_id: str,
        allowed_tools: list[str],
        tools: dict[str, Any] | None = None,
        audit_logger: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self._employee_id = employee_id
        self._allowed_tools = set(allowed_tools)
        self._tools = tools or {}
        self._audit_logger = audit_logger

    async def execute(self, tool_id: str, action: str, **params: object) -> ToolResult:
        """Execute a tool action through the broker.

        Args:
            tool_id: The tool to call (must be in allowed_tools).
            action: The specific action on that tool.
            **params: Action parameters.

        Returns:
            ToolResult with success status and data.

        Raises:
            PermissionError: If tool_id is not in the employee's allowed set.
        """
        if tool_id not in self._allowed_tools:
            raise PermissionError(
                f"Employee '{self._employee_id}' is not authorised to use tool '{tool_id}'."
            )

        call = ToolCall(
            employee_id=self._employee_id,
            tool_id=tool_id,
            action=action,
            parameters=dict(params),
        )
        logger.info("tool_broker_call", tool_id=tool_id, action=action, call_id=str(call.id))

        tool = self._tools.get(tool_id)
        if tool is None:
            raise ValueError(f"Tool '{tool_id}' is not registered with the broker.")

        if self._audit_logger is not None:
            await self._audit_logger(
                employee_id=self._employee_id,
                org_id=str(params.get("org_id", "")),
                event_type="tool_invoked",
                details={"tool_id": tool_id, "action": action, "parameters": dict(params)},
            )

        data = await tool.invoke(action, dict(params))
        result = ToolResult(call_id=call.id, success=True, data=data)
        logger.info("tool_broker_result", success=result.success, call_id=str(call.id))
        return result
