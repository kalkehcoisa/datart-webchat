from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from app.models.models import PresenceStatus, RoomVisibility, FriendRequestStatus


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if not 3 <= len(v) <= 50:
            raise ValueError("Username must be 3-50 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime
    presence: PresenceStatus


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    presence: PresenceStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PasswordResetRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_agent: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    last_used: datetime


class RoomCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: RoomVisibility = RoomVisibility.public

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("Room name must be 1-100 characters")
        return v


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str]
    visibility: RoomVisibility
    owner_id: uuid.UUID
    created_at: datetime
    member_count: Optional[int] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RoomMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    username: str
    presence: PresenceStatus
    is_admin: bool
    joined_at: datetime


class FriendRequestCreate(BaseModel):
    receiver_username: str
    message: Optional[str] = None


class FriendRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    message: Optional[str]
    status: FriendRequestStatus
    created_at: datetime
    sender: UserPublic
    receiver: UserPublic


class MessageCreate(BaseModel):
    content: Optional[str] = None
    reply_to_id: Optional[uuid.UUID] = None

    @field_validator("content")
    @classmethod
    def content_size(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v.encode("utf-8")) > 3072:
            raise ValueError("Message content exceeds 3KB limit")
        return v


class MessageEdit(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_size(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 3072:
            raise ValueError("Message content exceeds 3KB limit")
        return v


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    mime_type: str
    file_size: int
    comment: Optional[str]
    is_image: bool
    created_at: datetime


class ReplyMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    content: Optional[str]
    author: UserPublic
    is_deleted: bool


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    room_id: Optional[uuid.UUID]
    personal_chat_id: Optional[uuid.UUID]
    author: UserPublic
    content: Optional[str]
    reply_to: Optional[ReplyMessageOut]
    is_deleted: bool
    edited_at: Optional[datetime]
    created_at: datetime
    attachments: List[AttachmentOut] = []


class RoomBanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    banned_by_id: Optional[uuid.UUID]
    created_at: datetime
    banned_user: Optional[UserPublic]
    banned_by: Optional[UserPublic]


class InviteRequest(BaseModel):
    username: str


class PersonalChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    created_at: datetime
    other_user: Optional[UserPublic] = None
    unread_count: Optional[int] = None
