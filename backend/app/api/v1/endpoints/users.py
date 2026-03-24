from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import UserPublic
from app.api.v1.deps import get_current_user
from app.core.cache import cache_get, cache_set, key_user_public, USER_PUBLIC_TTL

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search", response_model=list[UserPublic])
async def search_users(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User)
        .where(User.username.ilike(f"%{q}%"))
        .limit(20)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserPublic)
async def get_user_public(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cached = await cache_get(key_user_public(user_id))
    if cached is not None:
        return UserPublic(**cached)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    out = UserPublic.model_validate(user)
    await cache_set(key_user_public(user_id), out.model_dump(), USER_PUBLIC_TTL)
    return out
