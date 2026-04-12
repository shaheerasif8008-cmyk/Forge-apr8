from __future__ import annotations

from uuid import uuid4

from factory.models.monitoring import PerformanceMetric
from factory.pipeline.monitor.drift_detector import detect_metric_drift


def test_drift_detector_emits_event_for_large_metric_shift() -> None:
    deployment_id = uuid4()
    org_id = uuid4()
    latest = PerformanceMetric(
        deployment_id=deployment_id,
        org_id=org_id,
        metric_name="avg_confidence",
        value=0.42,
        unit="ratio",
    )
    history = [
        PerformanceMetric(deployment_id=deployment_id, org_id=org_id, metric_name="avg_confidence", value=0.88, unit="ratio"),
        PerformanceMetric(deployment_id=deployment_id, org_id=org_id, metric_name="avg_confidence", value=0.86, unit="ratio"),
        PerformanceMetric(deployment_id=deployment_id, org_id=org_id, metric_name="avg_confidence", value=0.9, unit="ratio"),
    ]

    event = detect_metric_drift(
        deployment_id=deployment_id,
        org_id=org_id,
        latest_metric=latest,
        history=history,
    )

    assert event is not None
    assert event.category == "drift"
    assert event.title == "metric_drift_detected:avg_confidence"


def test_drift_detector_requires_sufficient_history() -> None:
    deployment_id = uuid4()
    org_id = uuid4()
    latest = PerformanceMetric(
        deployment_id=deployment_id,
        org_id=org_id,
        metric_name="tasks_total",
        value=12,
        unit="count",
    )
    history = [
        PerformanceMetric(deployment_id=deployment_id, org_id=org_id, metric_name="tasks_total", value=10, unit="count"),
        PerformanceMetric(deployment_id=deployment_id, org_id=org_id, metric_name="tasks_total", value=11, unit="count"),
    ]

    event = detect_metric_drift(
        deployment_id=deployment_id,
        org_id=org_id,
        latest_metric=latest,
        history=history,
    )

    assert event is None
