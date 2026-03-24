import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.models import (
    Room, RoomMember, RoomBan, RoomInvitation, User,
    RoomVisibility, Message, Attachment
)
from app.schemas.schemas import (
    RoomCreate, RoomOut, RoomUpdate, RoomMemberOut, RoomBanOut, InviteRequest
)
from app.api.v1.deps import get_current_user
from app.worker.tasks import broadcast_message, notify_user
from app.core.cache import (
    cache_get, cache_set, cache_delete, cache_delete_pattern,
    key_room, key_room_members, key_room_catalog,
    ROOM_INFO_TTL, ROOM_MEMBERS_TTL, ROOM_CATALOG_TTL,
)

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def _get_member(db, room_id, user_id):
    r = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
    )
    return r.scalar_one_or_none()


async def _require_admin(db, room_id, user_id):
    member = await _get_member(db, room_id, user_id)
    if not member or not member.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return member


@router.post("", response_model=RoomOut, status_code=201)
async def create_room(
    data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.name == data.name))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Room name already taken")
    room = Room(name=data.name, description=data.description, visibility=data.visibility, owner_id=current_user.id)
    db.add(room)
    await db.flush()
    member = RoomMember(room_id=room.id, user_id=current_user.id, is_admin=True)
    db.add(member)
    await db.commit()
    await db.refresh(room)
    count_r = await db.execute(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id))
    room_out = RoomOut.model_validate(room)
    room_out.member_count = count_r.scalar()
    await cache_delete(key_room_catalog())
    return room_out


@router.get("", response_model=list[RoomOut])
async def list_public_rooms(
    search: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not search:
        cached = await cache_get(key_room_catalog())
        if cached is not None:
            return cached

    q = select(Room).where(Room.visibility == RoomVisibility.public)
    if search:
        q = q.where(Room.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    rooms = result.scalars().all()
    out = []
    for room in rooms:
        count_r = await db.execute(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id))
        ro = RoomOut.model_validate(room)
        ro.member_count = count_r.scalar()
        out.append(ro)

    if not search:
        await cache_set(key_room_catalog(), [r.model_dump() for r in out], ROOM_CATALOG_TTL)
    return out


@router.get("/my", response_model=list[RoomOut])
async def my_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Room).join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_id == current_user.id)
    )
    rooms = result.scalars().all()
    out = []
    for room in rooms:
        count_r = await db.execute(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id))
        ro = RoomOut.model_validate(room)
        ro.member_count = count_r.scalar()
        out.append(ro)
    return out


@router.get("/invitations/pending")
async def pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RoomInvitation, Room, User)
        .join(Room, Room.id == RoomInvitation.room_id)
        .join(User, User.id == RoomInvitation.inviter_id)
        .where(RoomInvitation.invitee_id == current_user.id)
    )
    rows = result.all()
    return [
        {
            "room_id": str(inv.room_id),
            "room_name": room.name,
            "inviter": inviter.username,
            "created_at": inv.created_at,
        }
        for inv, room, inviter in rows
    ]


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cached = await cache_get(key_room(room_id))
    if cached:
        room_out = RoomOut(**cached)
        if room_out.visibility == RoomVisibility.private:
            member = await _get_member(db, room_id, current_user.id)
            if not member:
                raise HTTPException(status_code=403, detail="Access denied")
        return room_out

    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    member = await _get_member(db, room_id, current_user.id)
    if room.visibility == RoomVisibility.private and not member:
        raise HTTPException(status_code=403, detail="Access denied")
    count_r = await db.execute(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id))
    ro = RoomOut.model_validate(room)
    ro.member_count = count_r.scalar()
    await cache_set(key_room(room_id), ro.model_dump(), ROOM_INFO_TTL)
    return ro


@router.post("/{room_id}/join")
async def join_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.visibility == RoomVisibility.private:
        raise HTTPException(status_code=403, detail="Private room requires invitation")
    ban_r = await db.execute(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == current_user.id)
    )
    if ban_r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are banned from this room")
    existing = await _get_member(db, room_id, current_user.id)
    if existing:
        return {"detail": "Already a member"}
    db.add(RoomMember(room_id=room_id, user_id=current_user.id))
    await db.commit()
    await cache_delete(key_room_members(room_id), key_room(room_id))
    broadcast_message.delay(str(room_id), None, {"type": "member_joined", "user_id": str(current_user.id), "username": current_user.username})
    return {"detail": "Joined"}


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot leave. Delete the room instead.")
    member = await _get_member(db, room_id, current_user.id)
    if not member:
        raise HTTPException(status_code=400, detail="Not a member")
    await db.delete(member)
    await db.commit()
    await cache_delete(key_room_members(room_id), key_room(room_id))
    broadcast_message.delay(str(room_id), None, {"type": "member_left", "user_id": str(current_user.id)})
    return {"detail": "Left"}


@router.delete("/{room_id}")
async def delete_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete the room")
    await db.delete(room)
    await db.commit()
    await cache_delete(key_room(room_id), key_room_members(room_id), key_room_catalog())
    broadcast_message.delay(str(room_id), None, {"type": "room_deleted", "room_id": str(room_id)})
    return {"detail": "Deleted"}


@router.patch("/{room_id}", response_model=RoomOut)
async def update_room(
    room_id: uuid.UUID,
    data: RoomUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can update")
    if data.name:
        room.name = data.name
    if data.description is not None:
        room.description = data.description
    await db.commit()
    await db.refresh(room)
    await cache_delete(key_room(room_id), key_room_catalog())
    return RoomOut.model_validate(room)


@router.get("/{room_id}/members", response_model=list[RoomMemberOut])
async def list_members(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await _get_member(db, room_id, current_user.id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")

    cached = await cache_get(key_room_members(room_id))
    if cached is not None:
        return [RoomMemberOut(**m) for m in cached]

    result = await db.execute(
        select(RoomMember, User).join(User, User.id == RoomMember.user_id)
        .where(RoomMember.room_id == room_id)
    )
    rows = result.all()
    out = [
        RoomMemberOut(
            user_id=u.id, username=u.username, presence=u.presence,
            is_admin=m.is_admin, joined_at=m.joined_at
        )
        for m, u in rows
    ]
    await cache_set(key_room_members(room_id), [m.model_dump() for m in out], ROOM_MEMBERS_TTL)
    return out


@router.post("/{room_id}/members/{user_id}/ban")
async def ban_member(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(db, room_id, current_user.id)
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if str(user_id) == str(room.owner_id):
        raise HTTPException(status_code=400, detail="Cannot ban the owner")
    existing_ban = await db.execute(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == user_id)
    )
    if not existing_ban.scalar_one_or_none():
        db.add(RoomBan(room_id=room_id, user_id=user_id, banned_by_id=current_user.id))
    member = await _get_member(db, room_id, user_id)
    if member:
        await db.delete(member)
    await db.commit()
    await cache_delete(key_room_members(room_id), key_room(room_id))
    broadcast_message.delay(str(room_id), None, {"type": "member_banned", "user_id": str(user_id)})
    return {"detail": "Banned"}


@router.delete("/{room_id}/members/{user_id}/ban")
async def unban_member(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(db, room_id, current_user.id)
    r = await db.execute(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == user_id)
    )
    ban = r.scalar_one_or_none()
    if ban:
        await db.delete(ban)
        await db.commit()
    return {"detail": "Unbanned"}


@router.get("/{room_id}/bans", response_model=list[RoomBanOut])
async def list_bans(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(db, room_id, current_user.id)
    result = await db.execute(
        select(RoomBan)
        .options(selectinload(RoomBan.banned_user), selectinload(RoomBan.banned_by))
        .where(RoomBan.room_id == room_id)
    )
    return result.scalars().all()


@router.post("/{room_id}/members/{user_id}/admin")
async def grant_admin(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room or room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Owner required")
    member = await _get_member(db, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.is_admin = True
    await db.commit()
    await cache_delete(key_room_members(room_id))
    return {"detail": "Admin granted"}


@router.delete("/{room_id}/members/{user_id}/admin")
async def revoke_admin(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    admin_member = await _get_member(db, room_id, current_user.id)
    if not admin_member or not admin_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    if str(user_id) == str(room.owner_id):
        raise HTTPException(status_code=400, detail="Cannot revoke owner's admin")
    member = await _get_member(db, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.is_admin = False
    await db.commit()
    await cache_delete(key_room_members(room_id))
    return {"detail": "Admin revoked"}


@router.post("/{room_id}/members/{user_id}/remove")
async def remove_member(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ban_member(room_id, user_id, current_user, db)
    return {"detail": "Removed and banned"}


@router.post("/{room_id}/invite")
async def invite_user(
    room_id: uuid.UUID,
    data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await _get_member(db, room_id, current_user.id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    u_r = await db.execute(select(User).where(User.username == data.username))
    invitee = u_r.scalar_one_or_none()
    if not invitee:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await _get_member(db, room_id, invitee.id)
    if existing:
        return {"detail": "Already a member"}
    ban_r = await db.execute(
        select(RoomBan).where(RoomBan.room_id == room_id, RoomBan.user_id == invitee.id)
    )
    if ban_r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is banned from this room")
    inv_check = await db.execute(
        select(RoomInvitation).where(
            RoomInvitation.room_id == room_id, RoomInvitation.invitee_id == invitee.id
        )
    )
    if not inv_check.scalar_one_or_none():
        db.add(RoomInvitation(room_id=room_id, inviter_id=current_user.id, invitee_id=invitee.id))
        await db.commit()
    r = await db.execute(select(Room).where(Room.id == room_id))
    room = r.scalar_one_or_none()
    notify_user.delay(str(invitee.id), {
        "type": "room_invitation",
        "room_id": str(room_id),
        "room_name": room.name,
        "inviter": current_user.username,
    })
    return {"detail": "Invited"}


@router.post("/{room_id}/accept-invite")
async def accept_invite(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inv_r = await db.execute(
        select(RoomInvitation).where(
            RoomInvitation.room_id == room_id, RoomInvitation.invitee_id == current_user.id
        )
    )
    inv = inv_r.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    existing = await _get_member(db, room_id, current_user.id)
    if not existing:
        db.add(RoomMember(room_id=room_id, user_id=current_user.id))
    await db.delete(inv)
    await db.commit()
    await cache_delete(key_room_members(room_id), key_room(room_id))
    broadcast_message.delay(str(room_id), None, {"type": "member_joined", "user_id": str(current_user.id), "username": current_user.username})
    return {"detail": "Joined via invitation"}

