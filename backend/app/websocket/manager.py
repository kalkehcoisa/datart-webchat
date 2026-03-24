"""
WebSocket connection manager with Redis pub/sub.

Each uvicorn worker maintains its own in-process connection registry.
Messages are published to Redis channels; a background subscriber task
inside each worker forwards them to locally connected WebSockets.

Channel naming:
  room:<room_id>        — messages for a room
  chat:<chat_id>        — messages for a personal chat
  user:<user_id>        — per-user notifications (presence, friend events, etc.)
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._user_sockets: Dict[str, Set[WebSocket]] = {}
        self._room_sockets: Dict[str, Set[WebSocket]] = {}
        self._chat_sockets: Dict[str, Set[WebSocket]] = {}
        self._ws_user: Dict[WebSocket, str] = {}
        self._pubsub_task: asyncio.Task | None = None
        self._redis: aioredis.Redis | None = None

    async def startup(self):
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        logger.info("WebSocket manager started (Redis pub/sub listener active)")

    async def shutdown(self):
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()

    async def _pubsub_listener(self):
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("room:*", "chat:*", "user:*")
        try:
            async for raw in pubsub.listen():
                if raw["type"] != "pmessage":
                    continue
                channel: str = raw["channel"]
                data = raw["data"]
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                event = payload.pop("event", None)
                if event:
                    payload["type"] = event
                await self._dispatch(channel, payload)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("pub/sub listener crashed — restarting in 2s")
            await asyncio.sleep(2)
            self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        finally:
            await pubsub.aclose()

    async def _dispatch(self, channel: str, payload: dict):
        msg = json.dumps(payload)
        if channel.startswith("room:"):
            room_id = channel[5:]
            await self._send_to_set(self._room_sockets.get(room_id, set()), msg)
        elif channel.startswith("chat:"):
            chat_id = channel[5:]
            await self._send_to_set(self._chat_sockets.get(chat_id, set()), msg)
        elif channel.startswith("user:"):
            user_id = channel[5:]
            await self._send_to_set(self._user_sockets.get(user_id, set()), msg)

    @staticmethod
    async def _send_to_set(sockets: Set[WebSocket], msg: str):
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)

    def connect(self, user_id: str, ws: WebSocket):
        self._user_sockets.setdefault(user_id, set()).add(ws)
        self._ws_user[ws] = user_id

    def disconnect(self, ws: WebSocket) -> str | None:
        user_id = self._ws_user.pop(ws, None)
        if user_id:
            self._user_sockets.get(user_id, set()).discard(ws)
            if not self._user_sockets.get(user_id):
                self._user_sockets.pop(user_id, None)
        for s in self._room_sockets.values():
            s.discard(ws)
        for s in self._chat_sockets.values():
            s.discard(ws)
        return user_id

    def join_room(self, room_id: str, ws: WebSocket):
        self._room_sockets.setdefault(room_id, set()).add(ws)

    def leave_room(self, room_id: str, ws: WebSocket):
        self._room_sockets.get(room_id, set()).discard(ws)

    def join_chat(self, chat_id: str, ws: WebSocket):
        self._chat_sockets.setdefault(chat_id, set()).add(ws)

    def user_connection_count(self, user_id: str) -> int:
        return len(self._user_sockets.get(str(user_id), set()))

    async def publish_room(self, room_id, payload: dict):
        data = {**payload, "event": payload.get("type", "message")}
        data.pop("type", None)
        await self._redis.publish(f"room:{room_id}", json.dumps(data))

    async def publish_chat(self, chat_id, payload: dict):
        data = {**payload, "event": payload.get("type", "message")}
        data.pop("type", None)
        await self._redis.publish(f"chat:{chat_id}", json.dumps(data))

    async def publish_user(self, user_id, payload: dict):
        data = {**payload, "event": payload.get("type", "notification")}
        data.pop("type", None)
        await self._redis.publish(f"user:{user_id}", json.dumps(data))

    async def broadcast_room(self, room_id, payload: dict):
        await self.publish_room(room_id, payload)

    async def broadcast_chat(self, chat_id, payload: dict):
        await self.publish_chat(chat_id, payload)

    async def send_to_user(self, user_id, payload: dict):
        await self.publish_user(user_id, payload)


manager = ConnectionManager()
