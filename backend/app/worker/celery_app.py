from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "webchat",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.worker.tasks.broadcast_message": {"queue": "messages"},
        "app.worker.tasks.broadcast_presence": {"queue": "presence"},
        "app.worker.tasks.process_attachment": {"queue": "files"},
        "app.worker.tasks.notify_user": {"queue": "notifications"},
    },
    task_default_queue="default",
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_keepalive": True,
    },
    result_expires=300,
)
