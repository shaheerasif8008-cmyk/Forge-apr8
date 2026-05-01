"""Role-agnostic authority policy decisions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class AuthorityInput(BaseModel):
    action: str
    risk_tier: str = "medium"
    amount: float = 0.0
    external_impact: bool = False
    authority_matrix: dict[str, str] = Field(default_factory=dict)


class AuthorityDecision(BaseModel):
    decision: str
    rationale: str
    required_approver: str = ""


@register("policy_authority_engine")
class PolicyAuthorityEngine(QualityModule):
    """Central can-do-alone / approval-required / forbidden policy engine."""

    component_id = "policy_authority_engine"
    version = "1.0.0"
    config_schema = {
        "approval_amount_threshold": {"type": "float", "required": False, "description": "External-impact amount requiring approval.", "default": 10000.0},
        "required_approver": {"type": "str", "required": False, "description": "Default reviewer role.", "default": "supervisor"},
    }
    _forbidden_actions = {"file_tax_return", "sign_contract", "wire_funds", "provide_legal_advice"}

    async def initialize(self, config: dict[str, Any]) -> None:
        self._threshold = float(config.get("approval_amount_threshold", 10000.0))
        self._required_approver = str(config.get("required_approver", "supervisor"))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        payload = input_data if isinstance(input_data, AuthorityInput) else AuthorityInput.model_validate(input_data)
        configured = payload.authority_matrix.get(payload.action)
        if configured in {"never_do_alone", "forbidden"} or payload.action in self._forbidden_actions:
            return AuthorityDecision(decision="forbidden", rationale=f"{payload.action} is never do alone for this employee.")
        if configured in {"requires_approval", "approval_required"}:
            return AuthorityDecision(decision="requires_approval", rationale="Configured authority matrix requires approval.", required_approver=self._required_approver)
        if payload.risk_tier.lower() in {"high", "critical"} or (payload.external_impact and payload.amount >= self._threshold):
            return AuthorityDecision(decision="requires_approval", rationale="Risk, amount, or external impact requires approval.", required_approver=self._required_approver)
        return AuthorityDecision(decision="autonomous", rationale="Within configured authority.")
