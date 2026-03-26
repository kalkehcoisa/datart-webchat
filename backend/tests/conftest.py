import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.models import Friendship, Message, PersonalChat, Room, RoomMember, User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_redis_mock():
    pipeline_mock = MagicMock()
    pipeline_mock.incr = AsyncMock()
    pipeline_mock.expire = AsyncMock()
    pipeline_mock.execute = AsyncMock(return_value=[1, True])
    pipeline_mock.__aenter__ = AsyncMock(return_value=pipeline_mock)
    pipeline_mock.__aexit__ = AsyncMock(return_value=False)

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.scan_iter = AsyncMock(return_value=iter([]))
    redis_mock.publish = AsyncMock(return_value=0)
    redis_mock.pipeline = MagicMock(return_value=pipeline_mock)
    return redis_mock


@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async def init_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(init_models())
    yield engine
    asyncio.run(drop_models())

    asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    import tempfile

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    redis_mock = _make_redis_mock()

    with (
        tempfile.TemporaryDirectory() as tmp_upload_dir,
        patch("app.api.v1.endpoints.messages.settings") as mock_msg_settings,
        patch("app.api.v1.endpoints.files.settings") as mock_file_settings,
        patch("app.db.redis._redis", redis_mock),
        patch("app.db.redis.get_redis", new=AsyncMock(return_value=redis_mock)),
        patch("app.main.get_redis", new=AsyncMock(return_value=redis_mock)),
        patch("app.core.cache.get_redis", new=AsyncMock(return_value=redis_mock)),
        patch("app.api.v1.endpoints.messages.broadcast_message") as _bm,
        patch("app.api.v1.endpoints.messages.process_attachment") as _pa,
        patch("app.api.v1.endpoints.messages.notify_user") as _nu_msg,
        patch("app.api.v1.endpoints.rooms.broadcast_message") as _rm,
        patch("app.api.v1.endpoints.rooms.notify_user") as _nu_room,
        patch("app.api.v1.endpoints.friends.notify_user") as _nu_fr,
        patch("app.api.v1.endpoints.friends.broadcast_presence") as _bp,
        patch("app.websocket.handler.broadcast_presence") as _bp_ws,
        patch("app.websocket.manager.manager.startup", new=AsyncMock()),
        patch("app.websocket.manager.manager.shutdown", new=AsyncMock()),
    ):
        for m in [_bm, _pa, _nu_msg, _rm, _nu_room, _nu_fr, _bp, _bp_ws]:
            m.delay = MagicMock()

        from app.core.config import settings as real_settings

        mock_msg_settings.UPLOAD_DIR = tmp_upload_dir
        mock_msg_settings.MAX_FILE_SIZE_MB = real_settings.MAX_FILE_SIZE_MB
        mock_msg_settings.MAX_IMAGE_SIZE_MB = real_settings.MAX_IMAGE_SIZE_MB
        mock_file_settings.UPLOAD_DIR = tmp_upload_dir

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


async def create_user(
    db: AsyncSession, username: str, email: str, password: str = "password123"
) -> User:
    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}
