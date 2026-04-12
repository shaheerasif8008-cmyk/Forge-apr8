"""Drift detector: identifies behavioural deviation from baseline."""

from __future__ import annotations

from statistics import mean
from uuid import UUID

from factory.models.monitoring import EventSeverity, MonitoringEvent, PerformanceMetric

DRIFT_THRESHOLDS: dict[str, float] = {
    "avg_confidence": 0.2,
    "tasks_total": 0.5,
    "approval_rate": 0.35,
}


def detect_metric_drift(
    *,
    deployment_id: UUID,
    org_id: UUID,
    latest_metric: PerformanceMetric,
    history: list[PerformanceMetric],
) -> MonitoringEvent | None:
    """Compare the latest metric against recent history and emit a drift event if needed."""
    baseline_source = [metric.value for metric in history if metric.metric_name == latest_metric.metric_name]
    if len(baseline_source) < 3:
        return None

    baseline = mean(baseline_source)
    threshold = DRIFT_THRESHOLDS.get(latest_metric.metric_name, 0.4)
    if baseline == 0:
        delta_ratio = abs(latest_metric.value - baseline)
    else:
        delta_ratio = abs(latest_metric.value - baseline) / abs(baseline)

    if delta_ratio < threshold:
        return None

    return MonitoringEvent(
        deployment_id=deployment_id,
        org_id=org_id,
        severity=EventSeverity.WARNING,
        category="drift",
        title=f"metric_drift_detected:{latest_metric.metric_name}",
        detail={
            "metric_name": latest_metric.metric_name,
            "latest_value": latest_metric.value,
            "baseline": baseline,
            "delta_ratio": round(delta_ratio, 3),
            "threshold": threshold,
        },
    )
