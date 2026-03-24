import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, Query
from app.api.v1.endpoints import auth, rooms, messages, friends, files, users
from app.websocket.handler import websocket_handler
from app.websocket.manager import manager
from app.db.redis import get_redis, close_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.startup()
    yield
    await manager.shutdown()
    await close_redis()


app = FastAPI(title="WebChat", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/auth"):
        redis = await get_redis()
        ip = request.client.host if request.client else "unknown"
        key = f"rl:auth:{ip}"
        pipe = redis.pipeline()
        await pipe.incr(key)
        await pipe.expire(key, 60)
        results = await pipe.execute()
        count = results[0]
        if count > 20:
            return Response(content='{"detail":"Too many requests"}', status_code=429, media_type="application/json")
    return await call_next(request)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - t0) * 1000:.1f}ms"
    return response


app.include_router(auth.router, prefix="/api/v1")
app.include_router(rooms.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(friends.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    await websocket_handler(websocket, token)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
