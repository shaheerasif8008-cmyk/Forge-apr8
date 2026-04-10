"""Monitor worker: periodic health checks on all active deployments."""

from __future__ import annotations

import structlog

from factory.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="factory.workers.monitor_worker.health_sweep")
def health_sweep() -> None:
    """Check health of all active employee deployments."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(_async_health_sweep())


async def _async_health_sweep() -> None:
    """Async health sweep — queries DB for active deployments and checks each."""
    # TODO: query DB for active deployments, run health_checker.check_health on each
    logger.info("monitor_health_sweep_complete", checked=0)
