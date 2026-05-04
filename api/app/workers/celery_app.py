"""Raven — Celery Application"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "raven",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.scoring", "app.workers.analytics", "app.workers.report_pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=100,
    beat_schedule={
        # Daily scoring run at 02:00 UTC
        "daily-scoring": {
            "task": "app.workers.scoring.score_all_counterparties_task",
            "schedule": 86400,
        },
        # Market data refresh every hour
        "hourly-market-data": {
            "task": "app.workers.analytics.refresh_market_data_task",
            "schedule": 3600,
        },
    },
)
