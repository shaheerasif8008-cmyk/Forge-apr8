from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from factory.models.deployment import Deployment, DeploymentStatus
from factory.models.monitoring import PerformanceMetric
from factory.pipeline.monitor.health_checker import check_health
from factory.pipeline.monitor.drift_detector import detect_metric_drift
from factory.workers.monitor_worker import _async_health_sweep


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


@pytest.mark.anyio
async def test_health_checker_uses_runtime_api_health_endpoint(monkeypatch) -> None:
    deployment = Deployment(
        build_id=uuid4(),
        org_id=uuid4(),
        access_url="http://127.0.0.1:9999",
        status=DeploymentStatus.ACTIVE,
    )
    requested: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url):
            requested.append(url)
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr("factory.pipeline.monitor.health_checker.httpx.AsyncClient", FakeAsyncClient)

    event = await check_health(deployment)

    assert requested == ["http://127.0.0.1:9999/api/v1/health"]
    assert event.title == "health_ok"
    assert deployment.status == DeploymentStatus.ACTIVE
    assert deployment.health_last_checked is not None


@pytest.mark.anyio
async def test_monitor_worker_persists_updated_deployment_state(monkeypatch) -> None:
    deployment = Deployment(
        build_id=uuid4(),
        org_id=uuid4(),
        access_url="http://127.0.0.1:9999",
        status=DeploymentStatus.ACTIVE,
    )
    saved_deployments: list[Deployment] = []
    saved_events: list[object] = []
    saved_metrics: list[PerformanceMetric] = []

    @asynccontextmanager
    async def fake_session_factory():
        class FakeSession:
            async def commit(self) -> None:
                return None

        yield FakeSession()

    async def fake_list_active_deployments(session):
        return [deployment]

    async def fake_check_health(next_deployment):
        next_deployment.status = DeploymentStatus.DEGRADED
        return SimpleNamespace()

    async def fake_save_deployment(session, deployment_to_save):
        saved_deployments.append(deployment_to_save.model_copy(deep=True))
        return deployment_to_save

    async def fake_save_monitoring_event(session, event):
        saved_events.append(event)
        return event

    async def fake_save_performance_metric(session, metric):
        saved_metrics.append(metric)
        return metric

    async def fake_collect_runtime_metrics(next_deployment):
        return []

    monkeypatch.setattr("factory.workers.monitor_worker.get_session_factory", lambda: fake_session_factory)
    monkeypatch.setattr("factory.workers.monitor_worker.list_active_deployments", fake_list_active_deployments)
    monkeypatch.setattr("factory.workers.monitor_worker.check_health", fake_check_health)
    monkeypatch.setattr("factory.workers.monitor_worker.save_deployment", fake_save_deployment)
    monkeypatch.setattr("factory.workers.monitor_worker.save_monitoring_event", fake_save_monitoring_event)
    monkeypatch.setattr("factory.workers.monitor_worker.save_performance_metric", fake_save_performance_metric)
    monkeypatch.setattr("factory.workers.monitor_worker._collect_runtime_metrics", fake_collect_runtime_metrics)

    await _async_health_sweep()

    assert saved_deployments
    assert saved_deployments[0].status == DeploymentStatus.DEGRADED
    assert saved_events
    assert len(saved_metrics) == 1
