import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, or_
from app.db.session import AsyncSessionLocal
from app.core.security import decode_token
from app.models.models import User, Friendship, PresenceStatus
from app.websocket.manager import manager
from app.worker.tasks import broadcast_presence
from app.db.redis import get_redis

PRESENCE_KEY = "presence:{user_id}"
PRESENCE_TTL = 90


async def _get_friend_ids(db, user_id) -> list[str]:
    result = await db.execute(
        select(Friendship).where(
            or_(Friendship.user_a_id == user_id, Friendship.user_b_id == user_id)
        )
    )
    return [
        str(f.user_b_id) if str(f.user_a_id) == str(user_id) else str(f.user_a_id)
        for f in result.scalars().all()
    ]


async def _set_presence(user_id: str, status: PresenceStatus) -> list[str]:
    """
    Write presence to Redis immediately (fast path for real-time updates).
    Write to Postgres only when status changes, to avoid DB churn on every ping.
    """
    redis = await get_redis()
    prev = await redis.get(PRESENCE_KEY.format(user_id=user_id))

    if prev != status.value:
        await redis.setex(PRESENCE_KEY.format(user_id=user_id), PRESENCE_TTL, status.value)
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if user:
                user.presence = status
                await db.commit()
            friend_ids = await _get_friend_ids(db, user_id)
        return friend_ids

    await redis.expire(PRESENCE_KEY.format(user_id=user_id), PRESENCE_TTL)
    async with AsyncSessionLocal() as db:
        return await _get_friend_ids(db, user_id)


async def websocket_handler(websocket: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001)
        return

    user_id = payload["sub"]

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.id == user_id))
        if not r.scalar_one_or_none():
            await websocket.close(code=4001)
            return

    await websocket.accept()
    manager.connect(user_id, websocket)

    friend_ids = await _set_presence(user_id, PresenceStatus.online)
    broadcast_presence.delay(user_id, "online", friend_ids)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("type")

            if event == "pong":
                continue

            elif event == "join_room":
                if room_id := data.get("room_id"):
                    manager.join_room(room_id, websocket)

            elif event == "leave_room":
                if room_id := data.get("room_id"):
                    manager.leave_room(room_id, websocket)

            elif event == "join_chat":
                if chat_id := data.get("chat_id"):
                    manager.join_chat(chat_id, websocket)

            elif event == "afk":
                friend_ids = await _set_presence(user_id, PresenceStatus.afk)
                broadcast_presence.delay(user_id, "afk", friend_ids)

            elif event == "active":
                friend_ids = await _set_presence(user_id, PresenceStatus.online)
                broadcast_presence.delay(user_id, "online", friend_ids)

            elif event == "typing":
                room_id = data.get("room_id")
                chat_id = data.get("chat_id")
                typing_payload = {
                    "type": "typing",
                    "user_id": user_id,
                    "username": data.get("username", ""),
                }
                if room_id:
                    await manager.broadcast_room(room_id, typing_payload)
                elif chat_id:
                    await manager.broadcast_chat(chat_id, typing_payload)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
        if manager.user_connection_count(user_id) == 0:
            friend_ids = await _set_presence(user_id, PresenceStatus.offline)
            broadcast_presence.delay(user_id, "offline", friend_ids)
