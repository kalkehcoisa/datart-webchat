import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.db.session import get_db
from app.models.models import (
    User, FriendRequest, Friendship, UserBan, FriendRequestStatus
)
from app.schemas.schemas import FriendRequestCreate, FriendRequestOut, UserPublic
from app.api.v1.deps import get_current_user
from app.worker.tasks import notify_user, broadcast_presence
from app.core.cache import cache_get, cache_set, cache_delete, key_friends, FRIENDS_TTL
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/requests", status_code=201)
async def send_request(
    data: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(User).where(User.username == data.receiver_username))
    receiver = r.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    if str(receiver.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot add yourself")
    ban_r = await db.execute(
        select(UserBan).where(
            or_(
                (UserBan.banner_id == current_user.id) & (UserBan.banned_id == receiver.id),
                (UserBan.banner_id == receiver.id) & (UserBan.banned_id == current_user.id),
            )
        )
    )
    if ban_r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cannot send request to this user")
    existing_r = await db.execute(
        select(FriendRequest).where(
            or_(
                (FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == receiver.id),
                (FriendRequest.sender_id == receiver.id) & (FriendRequest.receiver_id == current_user.id),
            ),
            FriendRequest.status == FriendRequestStatus.pending,
        )
    )
    if existing_r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Request already pending")
    fr = FriendRequest(sender_id=current_user.id, receiver_id=receiver.id, message=data.message)
    db.add(fr)
    await db.commit()
    await db.refresh(fr)
    notify_user.delay(str(receiver.id), {
        "type": "friend_request",
        "from": current_user.username,
        "request_id": str(fr.id),
    })
    return {"detail": "Request sent", "id": str(fr.id)}


@router.get("/requests/pending", response_model=list[FriendRequestOut])
async def pending_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender), selectinload(FriendRequest.receiver))
        .where(
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == FriendRequestStatus.pending,
        )
    )
    return result.scalars().all()


@router.post("/requests/{request_id}/accept")
async def accept_request(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender))
        .where(FriendRequest.id == request_id, FriendRequest.receiver_id == current_user.id)
    )
    fr = r.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Request not found")
    fr.status = FriendRequestStatus.accepted
    a_id, b_id = sorted([fr.sender_id, fr.receiver_id], key=str)
    db.add(Friendship(user_a_id=a_id, user_b_id=b_id))
    await db.commit()
    await cache_delete(key_friends(str(current_user.id)), key_friends(str(fr.sender_id)))
    notify_user.delay(str(fr.sender_id), {
        "type": "friend_accepted",
        "by": current_user.username,
    })
    return {"detail": "Accepted"}


@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(FriendRequest).where(
            FriendRequest.id == request_id, FriendRequest.receiver_id == current_user.id
        )
    )
    fr = r.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Request not found")
    fr.status = FriendRequestStatus.rejected
    await db.commit()
    return {"detail": "Rejected"}


@router.get("", response_model=list[UserPublic])
async def list_friends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cached = await cache_get(key_friends(current_user.id))
    if cached is not None:
        return [UserPublic(**u) for u in cached]

    result = await db.execute(
        select(Friendship).options(
            selectinload(Friendship.user_a),
            selectinload(Friendship.user_b),
        ).where(
            or_(Friendship.user_a_id == current_user.id, Friendship.user_b_id == current_user.id)
        )
    )
    friendships = result.scalars().all()
    friends = []
    for f in friendships:
        other = f.user_b if str(f.user_a_id) == str(current_user.id) else f.user_a
        friends.append(UserPublic.model_validate(other))

    await cache_set(key_friends(current_user.id), [u.model_dump() for u in friends], FRIENDS_TTL)
    return friends


@router.delete("/{username}")
async def remove_friend(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u_r = await db.execute(select(User).where(User.username == username))
    other = u_r.scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    a_id, b_id = sorted([current_user.id, other.id], key=str)
    r = await db.execute(
        select(Friendship).where(Friendship.user_a_id == a_id, Friendship.user_b_id == b_id)
    )
    f = r.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Not friends")
    await db.delete(f)
    await db.commit()
    await cache_delete(key_friends(str(current_user.id)), key_friends(str(other.id)))
    return {"detail": "Removed"}


@router.post("/ban/{username}")
async def ban_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u_r = await db.execute(select(User).where(User.username == username))
    other = u_r.scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await db.execute(
        select(UserBan).where(UserBan.banner_id == current_user.id, UserBan.banned_id == other.id)
    )
    if existing.scalar_one_or_none():
        return {"detail": "Already banned"}
    a_id, b_id = sorted([current_user.id, other.id], key=str)
    f_r = await db.execute(
        select(Friendship).where(Friendship.user_a_id == a_id, Friendship.user_b_id == b_id)
    )
    f = f_r.scalar_one_or_none()
    if f:
        await db.delete(f)
    db.add(UserBan(banner_id=current_user.id, banned_id=other.id))
    await db.commit()
    await cache_delete(key_friends(str(current_user.id)), key_friends(str(other.id)))
    return {"detail": "Banned"}


@router.delete("/ban/{username}")
async def unban_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u_r = await db.execute(select(User).where(User.username == username))
    other = u_r.scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    r = await db.execute(
        select(UserBan).where(UserBan.banner_id == current_user.id, UserBan.banned_id == other.id)
    )
    ban = r.scalar_one_or_none()
    if ban:
        await db.delete(ban)
        await db.commit()
    return {"detail": "Unbanned"}
