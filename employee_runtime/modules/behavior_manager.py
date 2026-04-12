"""Local runtime behavior manager for direct commands, portal rules, and adaptive learning."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

SOURCE_PRIORITY = {
    "direct_command": 1,
    "portal_rule": 2,
    "adaptive_learning": 3,
}
URGENT_LEVELS = {"important", "urgent", "high", "critical"}


class BehaviorRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    rule_type: str = "quiet_hours"
    description: str
    after_hour: int = 17
    suppress_non_urgent: bool = True
    channels: list[str] = Field(default_factory=lambda: ["email", "messaging"])
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class BehaviorResolution(BaseModel):
    rule_type: str = "quiet_hours"
    channel: str
    urgency: str
    current_time: str
    applies: bool = False
    suppress_non_urgent: bool = False
    source: str = "default"
    matched_rule_id: str = ""
    rationale: str = "No matching behavior rule."


class BehaviorManager:
    def __init__(
        self,
        *,
        operational_memory: Any,
        audit_logger: Any,
        employee_id: str,
        org_id: str,
        timezone: str,
    ) -> None:
        self._operational_memory = operational_memory
        self._audit_logger = audit_logger
        self._employee_id = employee_id
        self._org_id = org_id
        self._timezone = timezone

    async def list_rules(self) -> list[BehaviorRule]:
        records = await self._operational_memory.list_by_category("behavior_rule")
        rules: list[BehaviorRule] = []
        for record in records:
            value = record.get("value", {})
            if isinstance(value, dict):
                rules.append(BehaviorRule.model_validate(value))
        return sorted(
            rules,
            key=lambda rule: (
                SOURCE_PRIORITY.get(rule.source, 99),
                rule.created_at,
            ),
        )

    async def store_rule(self, rule: BehaviorRule) -> BehaviorRule:
        await self._operational_memory.store(
            f"behavior:{rule.source}:{rule.rule_id}",
            rule.model_dump(mode="json"),
            "behavior_rule",
        )
        if self._audit_logger is not None:
            await self._audit_logger(
                employee_id=self._employee_id,
                org_id=self._org_id,
                event_type="behavior_rule_updated",
                details=rule.model_dump(mode="json"),
            )
        return rule

    async def add_direct_command(self, command: str) -> BehaviorRule:
        lowered = command.lower()
        suppress_non_urgent = not any(token in lowered for token in ("allow", "resume", "continue"))
        rule = BehaviorRule(
            source="direct_command",
            description=command,
            after_hour=self._parse_hour(command),
            suppress_non_urgent=suppress_non_urgent,
            metadata={"command": command},
        )
        return await self.store_rule(rule)

    async def set_portal_quiet_hours(
        self,
        *,
        rule_id: str,
        description: str,
        after_hour: int,
        suppress_non_urgent: bool,
        channels: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> BehaviorRule:
        rule = BehaviorRule(
            rule_id=rule_id,
            source="portal_rule",
            description=description,
            after_hour=after_hour,
            suppress_non_urgent=suppress_non_urgent,
            channels=channels,
            metadata=metadata or {},
        )
        return await self.store_rule(rule)

    async def add_adaptive_pattern(
        self,
        *,
        description: str,
        after_hour: int,
        suppress_non_urgent: bool,
        channels: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> BehaviorRule:
        rule = BehaviorRule(
            source="adaptive_learning",
            description=description,
            after_hour=after_hour,
            suppress_non_urgent=suppress_non_urgent,
            channels=channels,
            metadata=metadata or {},
        )
        return await self.store_rule(rule)

    async def resolve_quiet_hours(
        self,
        *,
        urgency: str,
        channel: str,
        current_time: datetime | None = None,
    ) -> BehaviorResolution:
        now = self._normalize_time(current_time)
        if urgency.lower() in URGENT_LEVELS:
            return BehaviorResolution(
                channel=channel,
                urgency=urgency,
                current_time=now.isoformat(),
                rationale="Urgent communication bypasses quiet-hours suppression.",
            )

        rules = await self.list_rules()
        applicable = [
            rule
            for rule in rules
            if rule.rule_type == "quiet_hours"
            and rule.active
            and channel in rule.channels
            and now.hour >= rule.after_hour
        ]
        if not applicable:
            return BehaviorResolution(
                channel=channel,
                urgency=urgency,
                current_time=now.isoformat(),
            )

        winning_rule = sorted(
            applicable,
            key=lambda rule: (
                SOURCE_PRIORITY.get(rule.source, 99),
                -datetime.fromisoformat(rule.created_at).timestamp(),
            ),
        )[0]
        return BehaviorResolution(
            channel=channel,
            urgency=urgency,
            current_time=now.isoformat(),
            applies=True,
            suppress_non_urgent=winning_rule.suppress_non_urgent,
            source=winning_rule.source,
            matched_rule_id=winning_rule.rule_id,
            rationale=winning_rule.description,
        )

    def _normalize_time(self, current_time: datetime | None) -> datetime:
        if current_time is not None:
            if current_time.tzinfo is None:
                return current_time.replace(tzinfo=ZoneInfo(self._timezone))
            return current_time.astimezone(ZoneInfo(self._timezone))
        return datetime.now(ZoneInfo(self._timezone))

    def _parse_hour(self, command: str) -> int:
        match = re.search(r"after\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", command.lower())
        if match is None:
            return 17
        hour = int(match.group(1))
        suffix = match.group(3)
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        return max(0, min(hour, 23))
