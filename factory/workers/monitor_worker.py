"""Monitor worker: periodic health checks on all active deployments."""

from __future__ import annotations

import structlog

from factory.database import get_session_factory, init_engine
from factory.models.monitoring import PerformanceMetric
from factory.persistence import (
    list_active_deployments,
    save_monitoring_event,
    save_performance_metric,
)
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
            checked += 1
        await session.commit()
    logger.info("monitor_health_sweep_complete", checked=checked)
