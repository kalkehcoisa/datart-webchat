import json
import os
import asyncio
import logging
from celery import Task
from PIL import Image
from app.worker.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task that provides a sync SQLAlchemy session."""
    _session_factory = None

    @property
    def session_factory(self):
        if self._session_factory is None:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
            engine = create_engine(sync_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
            self._session_factory = sessionmaker(bind=engine)
        return self._session_factory

    def get_session(self):
        return self.session_factory()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.worker.tasks.broadcast_message",
    max_retries=3,
    default_retry_delay=1,
)
def broadcast_message(self, room_id: str | None, chat_id: str | None, message_payload: dict):
    """
    Fan-out a message to all subscribers via Redis pub/sub.
    The WebSocket handler subscribes and forwards to connected clients.
    """
    import redis as sync_redis
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        if room_id:
            channel = f"room:{room_id}"
        else:
            channel = f"chat:{chat_id}"
        r.publish(channel, json.dumps({"event": "message", **message_payload}))
    except Exception as exc:
        logger.exception("broadcast_message failed")
        raise self.retry(exc=exc)
    finally:
        r.close()


@celery_app.task(
    bind=True,
    name="app.worker.tasks.broadcast_presence",
    max_retries=3,
    default_retry_delay=1,
)
def broadcast_presence(self, user_id: str, status: str, friend_ids: list[str]):
    import redis as sync_redis
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        payload = json.dumps({"event": "presence", "user_id": user_id, "status": status})
        pipe = r.pipeline(transaction=False)
        for fid in friend_ids:
            pipe.publish(f"user:{fid}", payload)
        pipe.execute()
    except Exception as exc:
        logger.exception("broadcast_presence failed")
        raise self.retry(exc=exc)
    finally:
        r.close()


@celery_app.task(
    bind=True,
    name="app.worker.tasks.notify_user",
    max_retries=3,
    default_retry_delay=1,
)
def notify_user(self, user_id: str, payload: dict):
    import redis as sync_redis
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        r.publish(f"user:{user_id}", json.dumps({"event": "notification", **payload}))
    except Exception as exc:
        logger.exception("notify_user failed")
        raise self.retry(exc=exc)
    finally:
        r.close()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.worker.tasks.process_attachment",
    max_retries=2,
)
def process_attachment(self, attachment_id: str):
    """
    Post-upload processing: generate thumbnail for images,
    update stored metadata.
    """
    from sqlalchemy import text
    session = self.get_session()
    try:
        row = session.execute(
            text("SELECT stored_filename, is_image FROM attachments WHERE id = :id"),
            {"id": attachment_id}
        ).fetchone()
        if not row or not row.is_image:
            return

        path = os.path.join(settings.UPLOAD_DIR, row.stored_filename)
        if not os.path.exists(path):
            return

        thumb_dir = os.path.join(settings.UPLOAD_DIR, "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, row.stored_filename)

        with Image.open(path) as img:
            img.thumbnail((400, 400), Image.LANCZOS)
            img.save(thumb_path, optimize=True, quality=80)

    except Exception as exc:
        logger.exception("process_attachment failed for %s", attachment_id)
        raise self.retry(exc=exc)
    finally:
        session.close()
