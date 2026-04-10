"""Celery application for the factory background workers."""

from __future__ import annotations

from celery import Celery

from factory.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forge_factory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["factory.workers.pipeline_worker", "factory.workers.monitor_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "factory.workers.pipeline_worker.*": {"queue": "pipeline"},
        "factory.workers.monitor_worker.*": {"queue": "monitor"},
    },
)
