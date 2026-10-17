from celery import Celery

from app.config import settings


celery_app = Celery("smartroll_fastapi", broker=settings.redis_url)
celery_app.conf.update(
    task_ignore_result=True,
    task_track_started=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)
celery_app.autodiscover_tasks(["app"])
