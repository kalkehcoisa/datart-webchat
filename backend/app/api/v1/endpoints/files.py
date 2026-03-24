import uuid
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import Attachment, Message, RoomMember, PersonalChat, User
from app.api.v1.deps import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{attachment_id}")
async def download_file(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    att = r.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="File not found")

    msg_r = await db.execute(select(Message).where(Message.id == att.message_id))
    msg = msg_r.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.room_id:
        member_r = await db.execute(
            select(RoomMember).where(
                RoomMember.room_id == msg.room_id,
                RoomMember.user_id == current_user.id,
            )
        )
        if not member_r.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")
    elif msg.personal_chat_id:
        chat_r = await db.execute(select(PersonalChat).where(PersonalChat.id == msg.personal_chat_id))
        chat = chat_r.scalar_one_or_none()
        if not chat or (str(chat.user_a_id) != str(current_user.id) and str(chat.user_b_id) != str(current_user.id)):
            raise HTTPException(status_code=403, detail="Access denied")

    path = os.path.join(settings.UPLOAD_DIR, att.stored_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=path,
        filename=att.filename,
        media_type=att.mime_type,
    )
