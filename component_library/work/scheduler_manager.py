"""scheduler_manager work capability component."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import ExecutiveAssistantInput, ExecutiveAssistantResult


@register("scheduler_manager")
class SchedulerManager(WorkCapability):
    config_schema = {
        "timezone": {"type": "str", "required": False, "description": "Default IANA timezone for scheduling operations.", "default": "America/New_York"},
    }
    component_id = "scheduler_manager"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._default_timezone = config.get("timezone", "America/New_York")

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_scheduler_manager.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ExecutiveAssistantInput):
            raise TypeError("SchedulerManager expects ExecutiveAssistantInput")
        return self.extract_schedule(input_data.request_text)

    def extract_schedule(self, request_text: str) -> ExecutiveAssistantResult:
        lowered = request_text.lower()
        schedule_updates: list[str] = []
        if "tomorrow" in lowered:
            schedule_updates.append(f"Follow up tomorrow ({self._default_timezone})")
        if "next week" in lowered:
            schedule_updates.append("Prepare a next-week scheduling window")
        if "meeting" in lowered or "calendar" in lowered:
            schedule_updates.append("Create or update a calendar hold")
        dates = re.findall(r"\b(?:monday|tuesday|wednesday|thursday|friday)\b", lowered)
        schedule_updates.extend([f"Track timing for {day.title()}" for day in dates])
        return ExecutiveAssistantResult(
            title="Scheduling Assessment",
            summary="Scheduling implications extracted from the request.",
            schedule_updates=schedule_updates,
            confidence_score=0.74 if schedule_updates else 0.55,
        )
