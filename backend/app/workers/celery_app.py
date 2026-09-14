"""Celery app (Architecture §4.7). Async exports + scheduled runs (D8)."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "minthrm_report_builder",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
