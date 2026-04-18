"""autonomy_manager quality and governance component."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.quality.schemas import (
    AutonomyContext,
    AutonomyDecision,
    ProposedAction,
)
from component_library.registry import register

DEFAULT_MATRIX_PATH = Path(__file__).resolve().parent / "autonomy_matrix.yaml"


@register("autonomy_manager")
class AutonomyManager(QualityModule):
    component_id = "autonomy_manager"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        matrix_path = Path(str(config.get("matrix_path", DEFAULT_MATRIX_PATH)))
        if not matrix_path.is_absolute():
            matrix_path = DEFAULT_MATRIX_PATH.parent / matrix_path
        self._matrix = yaml.safe_load(matrix_path.read_text()) or []
        self._tenant_overrides = dict(config.get("tenant_overrides", {}))
        self._required_approver = str(config.get("required_approver", "supervisor"))
        self._audit_logger = config.get("audit_logger")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=bool(self._matrix))

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_autonomy_manager.py"]

    def set_audit_logger(self, audit_logger: Any) -> None:
        self._audit_logger = audit_logger

    async def evaluate(self, input_data: Any) -> AutonomyDecision:
        payload = input_data if isinstance(input_data, dict) else {}
        action = ProposedAction.model_validate(payload.get("action", {}))
        context = AutonomyContext.model_validate(payload.get("context", {}))
        decision = self._decide(action, context)
        await self._log_decision(action, context, decision)
        return decision

    def _decide(self, action: ProposedAction, context: AutonomyContext) -> AutonomyDecision:
        tenant_policy = {
            **self._tenant_overrides,
            **context.tenant_policy,
        }
        forced = self._tenant_override_decision(tenant_policy)
        if forced is not None:
            return forced

        for rule in self._matrix:
            if self._matches(rule.get("match", {}), action, context):
                decision = rule.get("decision", {})
                return AutonomyDecision(
                    mode=str(decision.get("mode", "autonomous")),
                    required_approver=str(decision.get("approver", self._required_approver))
                    if decision.get("approver")
                    else None,
                    rationale=str(decision.get("rationale", f"Matched rule {rule.get('rule_id', 'unknown')}")),
                    matched_rule=str(rule.get("rule_id", "unknown")),
                )

        return AutonomyDecision(
            mode="autonomous",
            required_approver=None,
            rationale="No autonomy rule matched; defaulting to autonomous.",
            matched_rule="implicit_default",
        )

    def _tenant_override_decision(self, tenant_policy: dict[str, Any]) -> AutonomyDecision | None:
        if tenant_policy.get("force_approval_all"):
            return AutonomyDecision(
                mode="approval_required",
                required_approver=str(tenant_policy.get("required_approver", self._required_approver)),
                rationale="Tenant policy force_approval_all is enabled.",
                matched_rule="tenant_override.force_approval_all",
            )
        if tenant_policy.get("force_escalation"):
            return AutonomyDecision(
                mode="escalate",
                required_approver=str(tenant_policy.get("required_approver", self._required_approver)),
                rationale="Tenant policy force_escalation is enabled.",
                matched_rule="tenant_override.force_escalation",
            )
        return None

    def _matches(
        self,
        match: dict[str, Any],
        action: ProposedAction,
        context: AutonomyContext,
    ) -> bool:
        if not match:
            return True
        if "risk_tier" in match and context.risk_tier != str(match["risk_tier"]).upper():
            return False
        if "action_type" in match and action.type != match["action_type"]:
            return False
        if "confidence_min" in match and action.confidence < float(match["confidence_min"]):
            return False
        if "confidence_max" in match and action.confidence > float(match["confidence_max"]):
            return False
        recipients = int(action.estimated_impact.get("recipients", 0) or 0)
        if "impact_recipients_min" in match and recipients < int(match["impact_recipients_min"]):
            return False
        if "impact_recipients_max" in match and recipients > int(match["impact_recipients_max"]):
            return False
        return True

    async def _log_decision(
        self,
        action: ProposedAction,
        context: AutonomyContext,
        decision: AutonomyDecision,
    ) -> None:
        if self._audit_logger is None:
            return
        await self._audit_logger(
            employee_id=str(context.tenant_policy.get("employee_id", "employee-runtime")),
            org_id=str(context.tenant_policy.get("org_id", "")),
            event_type="autonomy_decision",
            details={
                "action": action.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
            },
        )
