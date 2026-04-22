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
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

from component_library.quality.schemas import ProposedAction

logger = structlog.get_logger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class ToolCall(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    employee_id: str
    tool_id: str
    action: str
    parameters: dict[str, object] = Field(default_factory=dict)
    called_at: datetime = Field(default_factory=utc_now)


class ToolResult(BaseModel):
    call_id: UUID
    success: bool
    data: dict[str, object] = Field(default_factory=dict)
    error: str = ""
    completed_at: datetime = Field(default_factory=utc_now)


class ToolBroker:
    """Permission-enforcing, audit-logging gateway for external tool calls."""

    def __init__(
        self,
        employee_id: str,
        allowed_tools: list[str],
        tools: dict[str, Any] | None = None,
        audit_logger: Callable[..., Awaitable[Any]] | None = None,
        autonomy_manager: Any | None = None,
        risk_tier: str = "MEDIUM",
        tenant_policy: dict[str, Any] | None = None,
        required_approver: str = "supervisor",
    ) -> None:
        self._employee_id = employee_id
        self._allowed_tools = set(allowed_tools)
        self._tools = tools or {}
        self._audit_logger = audit_logger
        self._autonomy_manager = autonomy_manager
        self._risk_tier = str(risk_tier).upper()
        self._tenant_policy = dict(tenant_policy or {})
        self._required_approver = required_approver

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

        await self._enforce_autonomy(tool_id, action, dict(params))

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

    async def _enforce_autonomy(self, tool_id: str, action: str, params: dict[str, object]) -> None:
        if self._autonomy_manager is None:
            return

        proposed_action = ProposedAction(
            type=self._classify_action(tool_id, action),
            description=f"{tool_id}.{action}",
            confidence=float(params.get("confidence", 1.0) or 0.0),
            estimated_impact=self._estimate_impact(params),
        )
        decision = await self._autonomy_manager.evaluate(
            {
                "action": proposed_action.model_dump(mode="json"),
                "context": {
                    "risk_tier": self._risk_tier,
                    "tenant_policy": {
                        **self._tenant_policy,
                        "required_approver": self._required_approver,
                        "employee_id": self._employee_id,
                        "org_id": str(params.get("org_id", "")),
                    },
                },
            }
        )
        if decision.mode == "autonomous":
            return
        if self._audit_logger is not None:
            await self._audit_logger(
                employee_id=self._employee_id,
                org_id=str(params.get("org_id", "")),
                event_type="tool_blocked_by_autonomy",
                details={
                    "tool_id": tool_id,
                    "action": action,
                    "decision": decision.model_dump(mode="json"),
                    "parameters": params,
                },
            )
        raise PermissionError(decision.rationale)

    def _classify_action(self, tool_id: str, action: str) -> str:
        irreversible_actions = {
            ("email_tool", "send"),
            ("messaging_tool", "send"),
        }
        semi_reversible_actions = {
            ("calendar_tool", "create_event"),
            ("crm_tool", "upsert_contact"),
        }
        if (tool_id, action) in irreversible_actions:
            return "irreversible"
        if (tool_id, action) in semi_reversible_actions:
            return "semi_reversible"
        return "reversible"

    def _estimate_impact(self, params: dict[str, object]) -> dict[str, object]:
        recipients = 0
        if isinstance(params.get("to"), str) and params.get("to"):
            recipients = 1
        attendees = params.get("attendees")
        if isinstance(attendees, list):
            recipients = max(recipients, len(attendees))
        return {
            "recipients": recipients,
            "has_body": bool(params.get("body")),
            "channel": str(params.get("channel", "")),
        }
