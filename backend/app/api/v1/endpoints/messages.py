import uuid
import os
import aiofiles
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.worker.tasks import broadcast_message, process_attachment, notify_user
from app.models.models import (
    Message, RoomMember, PersonalChat, Attachment,
    User, Room, Friendship, UserBan, MessageRead
)
from app.schemas.schemas import MessageCreate, MessageEdit, MessageOut, AttachmentOut
from app.api.v1.deps import get_current_user
from app.core.config import settings
import mimetypes

router = APIRouter(tags=["messages"])

ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


async def _load_message(db, message_id) -> Message:
    r = await db.execute(
        select(Message)
        .options(
            selectinload(Message.author),
            selectinload(Message.attachments),
            selectinload(Message.reply_to).options(selectinload(Message.author)),
        )
        .where(Message.id == message_id)
    )
    msg = r.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


async def _check_room_access(db, room_id, user_id):
    r = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this room")


async def _check_chat_access(db, chat_id, user_id):
    r = await db.execute(select(PersonalChat).where(PersonalChat.id == chat_id))
    chat = r.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if str(chat.user_a_id) != str(user_id) and str(chat.user_b_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return chat


async def _are_friends(db, user_a_id, user_b_id) -> bool:
    r = await db.execute(
        select(Friendship).where(
            ((Friendship.user_a_id == user_a_id) & (Friendship.user_b_id == user_b_id)) |
            ((Friendship.user_a_id == user_b_id) & (Friendship.user_b_id == user_a_id))
        )
    )
    return r.scalar_one_or_none() is not None


async def _is_banned(db, banner_id, banned_id) -> bool:
    r = await db.execute(
        select(UserBan).where(
            ((UserBan.banner_id == banner_id) & (UserBan.banned_id == banned_id)) |
            ((UserBan.banner_id == banned_id) & (UserBan.banned_id == banner_id))
        )
    )
    return r.scalar_one_or_none() is not None


def _message_to_dict(msg: Message) -> dict:
    reply = None
    if msg.reply_to and not msg.reply_to.is_deleted:
        reply_author = msg.reply_to.author
        reply = {
            "id": str(msg.reply_to.id),
            "content": msg.reply_to.content,
            "author": {
                "id": str(reply_author.id) if reply_author else None,
                "username": reply_author.username if reply_author else "[deleted]",
                "presence": reply_author.presence.value if reply_author else "offline",
            },
            "is_deleted": msg.reply_to.is_deleted,
        }
    author = msg.author
    return {
        "id": str(msg.id),
        "room_id": str(msg.room_id) if msg.room_id else None,
        "personal_chat_id": str(msg.personal_chat_id) if msg.personal_chat_id else None,
        "author": {
            "id": str(author.id) if author else None,
            "username": author.username if author else "[deleted]",
            "presence": author.presence.value if author else "offline",
        },
        "content": msg.content if not msg.is_deleted else None,
        "reply_to": reply,
        "is_deleted": msg.is_deleted,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "created_at": msg.created_at.isoformat(),
        "attachments": [
            {
                "id": str(a.id),
                "filename": a.filename,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "comment": a.comment,
                "is_image": a.is_image,
            }
            for a in msg.attachments
        ],
    }


@router.get("/rooms/{room_id}/messages")
async def get_room_messages(
    room_id: uuid.UUID,
    before: uuid.UUID = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_room_access(db, room_id, current_user.id)
    limit = min(limit, 100)
    q = (
        select(Message)
        .options(
            selectinload(Message.author),
            selectinload(Message.attachments),
            selectinload(Message.reply_to).options(selectinload(Message.author)),
        )
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    if before:
        ref = await db.execute(select(Message).where(Message.id == before))
        ref_msg = ref.scalar_one_or_none()
        if ref_msg:
            q = q.where(
                (Message.created_at < ref_msg.created_at) |
                ((Message.created_at == ref_msg.created_at) & (Message.id < ref_msg.id))
            )
    result = await db.execute(q)
    msgs = result.scalars().all()
    return list(reversed([_message_to_dict(m) for m in msgs]))


@router.post("/rooms/{room_id}/messages")
async def send_room_message(
    room_id: uuid.UUID,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_room_access(db, room_id, current_user.id)
    msg = Message(
        room_id=room_id,
        author_id=current_user.id,
        content=data.content,
        reply_to_id=data.reply_to_id,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    msg = await _load_message(db, msg.id)
    await db.commit()
    msg_dict = _message_to_dict(msg)
    broadcast_message.delay(str(room_id), None, {"type": "message", **msg_dict})
    return msg_dict


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: uuid.UUID,
    data: MessageEdit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _load_message(db, message_id)
    if str(msg.author_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your message")
    if msg.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot edit a deleted message")
    msg.content = data.content
    msg.edited_at = datetime.now(timezone.utc)
    await db.commit()
    msg = await _load_message(db, message_id)
    payload = {"type": "message_edited", **_message_to_dict(msg)}
    if msg.room_id:
        broadcast_message.delay(str(msg.room_id), None, payload)
    elif msg.personal_chat_id:
        broadcast_message.delay(None, str(msg.personal_chat_id), payload)
    return _message_to_dict(msg)


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _load_message(db, message_id)
    is_author = str(msg.author_id) == str(current_user.id)
    is_admin = False
    if msg.room_id:
        r = await db.execute(
            select(RoomMember).where(
                RoomMember.room_id == msg.room_id,
                RoomMember.user_id == current_user.id,
                RoomMember.is_admin == True,
            )
        )
        is_admin = r.scalar_one_or_none() is not None
    if not is_author and not is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    msg.is_deleted = True
    msg.content = None
    await db.commit()
    payload = {"type": "message_deleted", "message_id": str(message_id)}
    if msg.room_id:
        broadcast_message.delay(str(msg.room_id), None, payload)
    elif msg.personal_chat_id:
        broadcast_message.delay(None, str(msg.personal_chat_id), payload)
    return {"detail": "Deleted"}


@router.get("/chats", response_model=list)
async def list_personal_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PersonalChat, User).join(
            User,
            (User.id == PersonalChat.user_a_id) | (User.id == PersonalChat.user_b_id)
        ).where(
            ((PersonalChat.user_a_id == current_user.id) | (PersonalChat.user_b_id == current_user.id)) &
            (User.id != current_user.id)
        )
    )
    rows = result.all()
    out = []
    for chat, other in rows:
        is_banned = await _is_banned(db, current_user.id, other.id)
        out.append({
            "id": str(chat.id),
            "other_user": {"id": str(other.id), "username": other.username, "presence": other.presence.value},
            "created_at": chat.created_at.isoformat(),
            "frozen": is_banned,
        })

    # Also include chats where the other participant was deleted (user_a or user_b is NULL)
    deleted_result = await db.execute(
        select(PersonalChat).where(
            ((PersonalChat.user_a_id == current_user.id) & (PersonalChat.user_b_id == None)) |
            ((PersonalChat.user_b_id == current_user.id) & (PersonalChat.user_a_id == None))
        )
    )
    for chat in deleted_result.scalars().all():
        out.append({
            "id": str(chat.id),
            "other_user": {"id": None, "username": "[deleted]", "presence": "offline"},
            "created_at": chat.created_at.isoformat(),
            "frozen": True,
        })
    return out


@router.post("/chats/{username}")
async def open_personal_chat(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u_r = await db.execute(select(User).where(User.username == username))
    other = u_r.scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")

    is_banned = await _is_banned(db, current_user.id, other.id)
    is_friend = await _are_friends(db, current_user.id, other.id)

    if not is_friend and not is_banned:
        raise HTTPException(status_code=403, detail="You must be friends to message")

    a_id, b_id = sorted([current_user.id, other.id], key=str)
    r = await db.execute(
        select(PersonalChat).where(PersonalChat.user_a_id == a_id, PersonalChat.user_b_id == b_id)
    )
    chat = r.scalar_one_or_none()

    if not chat:
        if is_banned:
            raise HTTPException(status_code=403, detail="Cannot open chat with this user")
        chat = PersonalChat(user_a_id=a_id, user_b_id=b_id)
        db.add(chat)
        await db.commit()
        await db.refresh(chat)

    return {
        "id": str(chat.id),
        "other_user": {"id": str(other.id), "username": other.username, "presence": other.presence.value},
        "created_at": chat.created_at.isoformat(),
        "frozen": is_banned,
    }


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: uuid.UUID,
    before: uuid.UUID = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_chat_access(db, chat_id, current_user.id)
    limit = min(limit, 100)
    q = (
        select(Message)
        .options(
            selectinload(Message.author),
            selectinload(Message.attachments),
            selectinload(Message.reply_to).options(selectinload(Message.author)),
        )
        .where(Message.personal_chat_id == chat_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    if before:
        ref = await db.execute(select(Message).where(Message.id == before))
        ref_msg = ref.scalar_one_or_none()
        if ref_msg:
            q = q.where(
                (Message.created_at < ref_msg.created_at) |
                ((Message.created_at == ref_msg.created_at) & (Message.id < ref_msg.id))
            )
    result = await db.execute(q)
    msgs = result.scalars().all()
    return list(reversed([_message_to_dict(m) for m in msgs]))


@router.post("/chats/{chat_id}/messages")
async def send_chat_message(
    chat_id: uuid.UUID,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await _check_chat_access(db, chat_id, current_user.id)
    other_id = chat.user_b_id if str(chat.user_a_id) == str(current_user.id) else chat.user_a_id
    if await _is_banned(db, current_user.id, other_id):
        raise HTTPException(status_code=403, detail="Cannot message this user")
    if not await _are_friends(db, current_user.id, other_id):
        raise HTTPException(status_code=403, detail="Must be friends to message")
    msg = Message(
        personal_chat_id=chat_id,
        author_id=current_user.id,
        content=data.content,
        reply_to_id=data.reply_to_id,
    )
    db.add(msg)
    await db.flush()
    msg = await _load_message(db, msg.id)
    await db.commit()
    msg_dict = _message_to_dict(msg)
    payload = {"type": "message", **msg_dict}
    broadcast_message.delay(None, str(chat_id), payload)
    notify_user.delay(str(other_id), payload)
    return msg_dict


@router.post("/upload")
async def upload_file(
    message_id: uuid.UUID = Form(...),
    comment: str = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _load_message(db, message_id)
    if str(msg.author_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your message")

    original_filename = file.filename or "upload"
    mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    is_image = mime_type in ALLOWED_IMAGES
    max_bytes = (settings.MAX_IMAGE_SIZE_MB if is_image else settings.MAX_FILE_SIZE_MB) * 1024 * 1024

    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    ext = os.path.splitext(original_filename)[1]
    stored_name = f"{uuid.uuid4()}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, stored_name)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)

    attachment = Attachment(
        message_id=message_id,
        uploader_id=current_user.id,
        filename=original_filename,
        stored_filename=stored_name,
        mime_type=mime_type,
        file_size=len(content),
        comment=comment,
        is_image=is_image,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    process_attachment.delay(str(attachment.id))
    return AttachmentOut.model_validate(attachment)
