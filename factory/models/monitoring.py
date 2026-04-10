"""MonitoringEvent and PerformanceMetric models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    deployment_id: UUID
    org_id: UUID
    severity: EventSeverity = EventSeverity.INFO
    category: str = Field(description="health | drift | performance | anomaly")
    title: str
    detail: dict[str, object] = Field(default_factory=dict)
    resolved: bool = False
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class PerformanceMetric(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    deployment_id: UUID
    org_id: UUID
    metric_name: str
    value: float
    unit: str = ""
    window_minutes: int = 60
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
