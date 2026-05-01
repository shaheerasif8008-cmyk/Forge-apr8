"""Type 5: Policy changes — client-controlled business rules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    """A client-defined behavioural rule applied to their employee."""

    rule_id: str
    description: str
    condition: str = Field(description="e.g. 'time_of_day > 17:00'")
    action: str = Field(description="e.g. 'suppress_non_urgent_messages'")
    priority: int = Field(2, description="1=direct command, 2=portal rule, 3=adaptive")
    active: bool = True


class PolicyManager:
    def __init__(self) -> None:
        self._policies: dict[str, list[PolicyRule]] = {}

    def list_rules(self, deployment_id: str) -> list[PolicyRule]:
        return list(self._policies.get(deployment_id, []))

    def add_rule(self, deployment_id: str, rule: PolicyRule) -> PolicyRule:
        self._policies.setdefault(deployment_id, []).append(rule)
        return rule

    def deactivate_rule(self, deployment_id: str, rule_id: str) -> PolicyRule | None:
        for rule in self._policies.get(deployment_id, []):
            if rule.rule_id == rule_id:
                rule.active = False
                return rule
        return None


policy_manager = PolicyManager()
