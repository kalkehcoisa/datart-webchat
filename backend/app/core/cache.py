import json
import logging
from typing import Any
from app.db.redis import get_redis

logger = logging.getLogger(__name__)

PREFIX = "cache:"


async def cache_get(key: str) -> Any | None:
    try:
        redis = await get_redis()
        raw = await redis.get(f"{PREFIX}{key}")
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("cache_get failed for key=%s", key, exc_info=True)
        return None


async def cache_set(key: str, value: Any, ttl: int):
    try:
        redis = await get_redis()
        await redis.setex(f"{PREFIX}{key}", ttl, json.dumps(value, default=str))
    except Exception:
        logger.warning("cache_set failed for key=%s", key, exc_info=True)


async def cache_delete(*keys: str):
    try:
        redis = await get_redis()
        await redis.delete(*[f"{PREFIX}{k}" for k in keys])
    except Exception:
        logger.warning("cache_delete failed for keys=%s", keys, exc_info=True)


async def cache_delete_pattern(pattern: str):
    try:
        redis = await get_redis()
        keys = [k async for k in redis.scan_iter(f"{PREFIX}{pattern}")]
        if keys:
            await redis.delete(*keys)
    except Exception:
        logger.warning("cache_delete_pattern failed for pattern=%s", pattern, exc_info=True)


ROOM_INFO_TTL = 300
ROOM_MEMBERS_TTL = 60
ROOM_CATALOG_TTL = 30
FRIENDS_TTL = 120
USER_PUBLIC_TTL = 300


def key_room(room_id) -> str:
    return f"room:{room_id}"


def key_room_members(room_id) -> str:
    return f"room:{room_id}:members"


def key_room_catalog() -> str:
    return "rooms:public"


def key_friends(user_id) -> str:
    return f"friends:{user_id}"


def key_user_public(user_id) -> str:
    return f"user:{user_id}:public"
