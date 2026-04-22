"""Monitor worker: periodic health checks on all active deployments."""

from __future__ import annotations

import httpx
import structlog

from factory.database import get_session_factory, init_engine
from factory.models.monitoring import PerformanceMetric
from factory.persistence import (
    list_active_deployments,
    list_recent_performance_metrics,
    save_deployment,
    save_monitoring_event,
    save_performance_metric,
)
from factory.pipeline.monitor.drift_detector import detect_metric_drift
from factory.pipeline.monitor.health_checker import check_health
from factory.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="factory.workers.monitor_worker.health_sweep")
def health_sweep() -> None:
    """Check health of all active employee deployments."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(_async_health_sweep())


async def _async_health_sweep() -> None:
    """Async health sweep — queries DB for active deployments and checks each."""
    try:
        session_factory = get_session_factory()
    except RuntimeError:
        init_engine()
        session_factory = get_session_factory()

    checked = 0
    async with session_factory() as session:
        deployments = await list_active_deployments(session)
        for deployment in deployments:
            event = await check_health(deployment)
            await save_deployment(session, deployment)
            await save_monitoring_event(session, event)
            await save_performance_metric(
                session,
                PerformanceMetric(
                    deployment_id=deployment.id,
                    org_id=deployment.org_id,
                    metric_name="health_checks_total",
                    value=1.0,
                    unit="count",
                ),
            )
            for metric in await _collect_runtime_metrics(deployment):
                saved_metric = await save_performance_metric(session, metric)
                history = await list_recent_performance_metrics(
                    session,
                    deployment.id,
                    metric_name=saved_metric.metric_name,
                    limit=12,
                )
                drift_event = detect_metric_drift(
                    deployment_id=deployment.id,
                    org_id=deployment.org_id,
                    latest_metric=saved_metric,
                    history=history[1:],
                )
                if drift_event is not None:
                    await save_monitoring_event(session, drift_event)
            checked += 1
        await session.commit()
    logger.info("monitor_health_sweep_complete", checked=checked)


async def _collect_runtime_metrics(deployment) -> list[PerformanceMetric]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{deployment.access_url}/api/v1/metrics")
        if response.status_code != 200:
            return []
        payload = response.json()
    except httpx.RequestError:
        return []

    metrics: list[PerformanceMetric] = []
    numeric_metrics = {
        "tasks_total": float(payload.get("tasks_total", 0.0)),
        "avg_confidence": float(payload.get("avg_confidence", 0.0)),
    }
    approval_mix = payload.get("approval_mix", {})
    if isinstance(approval_mix, dict):
        total_decisions = sum(float(value) for value in approval_mix.values()) or 0.0
        numeric_metrics["approval_rate"] = 0.0 if total_decisions == 0 else float(approval_mix.get("approve", 0.0)) / total_decisions

    for metric_name, value in numeric_metrics.items():
        metrics.append(
            PerformanceMetric(
                deployment_id=deployment.id,
                org_id=deployment.org_id,
                metric_name=metric_name,
                value=value,
                unit="ratio" if metric_name in {"avg_confidence", "approval_rate"} else "count",
            )
        )
    return metrics
