"""Measure employee ROI from completed work."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class RoiMetricInput(BaseModel):
    tasks_completed: int = 0
    minutes_saved: float = 0.0
    errors_caught: int = 0
    rework_minutes: float = 0.0
    revenue_influenced: float = 0.0
    hourly_rate: float | None = None


class RoiMetricReport(BaseModel):
    hours_saved: float
    net_minutes_saved: float
    labor_value_usd: float
    revenue_influenced: float
    roi_signals: dict[str, Any] = Field(default_factory=dict)


@register("roi_meter")
class RoiMeter(QualityModule):
    """Computes client-visible value signals for employee work."""

    component_id = "roi_meter"
    version = "1.0.0"
    config_schema = {
        "default_hourly_rate": {"type": "float", "required": False, "description": "Blended client hourly rate for saved work.", "default": 100.0},
    }

    async def initialize(self, config: dict[str, Any]) -> None:
        self._default_hourly_rate = float(config.get("default_hourly_rate", 100.0))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        payload = input_data if isinstance(input_data, RoiMetricInput) else RoiMetricInput.model_validate(input_data)
        net_minutes = max(0.0, payload.minutes_saved - payload.rework_minutes)
        hours_saved = round(payload.minutes_saved / 60.0, 2)
        hourly_rate = payload.hourly_rate if payload.hourly_rate is not None else self._default_hourly_rate
        return RoiMetricReport(
            hours_saved=hours_saved,
            net_minutes_saved=net_minutes,
            labor_value_usd=round(hours_saved * hourly_rate, 2),
            revenue_influenced=round(payload.revenue_influenced, 2),
            roi_signals={
                "tasks_completed": payload.tasks_completed,
                "errors_caught": payload.errors_caught,
                "rework_minutes": payload.rework_minutes,
            },
        )
