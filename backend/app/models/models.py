import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, Boolean, DateTime, Integer, ForeignKey,
    UniqueConstraint, Enum as SAEnum, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
import enum
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class PresenceStatus(str, enum.Enum):
    online = "online"
    afk = "afk"
    offline = "offline"


class RoomVisibility(str, enum.Enum):
    public = "public"
    private = "private"


class FriendRequestStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    presence: Mapped[PresenceStatus] = mapped_column(SAEnum(PresenceStatus), default=PresenceStatus.offline)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    owned_rooms: Mapped[list["Room"]] = relationship(back_populates="owner", foreign_keys="Room.owner_id")
    memberships: Mapped[list["RoomMember"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sent_requests: Mapped[list["FriendRequest"]] = relationship(back_populates="sender", foreign_keys="FriendRequest.sender_id", cascade="all, delete-orphan")
    received_requests: Mapped[list["FriendRequest"]] = relationship(back_populates="receiver", foreign_keys="FriendRequest.receiver_id", cascade="all, delete-orphan")
    friendships_a: Mapped[list["Friendship"]] = relationship(back_populates="user_a", foreign_keys="Friendship.user_a_id", cascade="all, delete-orphan")
    friendships_b: Mapped[list["Friendship"]] = relationship(back_populates="user_b", foreign_keys="Friendship.user_b_id", cascade="all, delete-orphan")
    bans_issued: Mapped[list["UserBan"]] = relationship(back_populates="banner", foreign_keys="UserBan.banner_id", cascade="all, delete-orphan")
    bans_received: Mapped[list["UserBan"]] = relationship(back_populates="banned", foreign_keys="UserBan.banned_id", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="author")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="uploader")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token: Mapped[str] = mapped_column(String(512), unique=True)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    visibility: Mapped[RoomVisibility] = mapped_column(SAEnum(RoomVisibility), default=RoomVisibility.public)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="owned_rooms", foreign_keys=[owner_id])
    members: Mapped[list["RoomMember"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    bans: Mapped[list["RoomBan"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    invitations: Mapped[list["RoomInvitation"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["Room"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class RoomBan(Base):
    __tablename__ = "room_bans"
    __table_args__ = (UniqueConstraint("room_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    banned_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["Room"] = relationship(back_populates="bans")
    banned_user: Mapped["User"] = relationship(foreign_keys=[user_id])
    banned_by: Mapped["User"] = relationship(foreign_keys=[banned_by_id])


class RoomInvitation(Base):
    __tablename__ = "room_invitations"
    __table_args__ = (UniqueConstraint("room_id", "invitee_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    inviter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invitee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["Room"] = relationship(back_populates="invitations")
    inviter: Mapped["User"] = relationship(foreign_keys=[inviter_id])
    invitee: Mapped["User"] = relationship(foreign_keys=[invitee_id])


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[FriendRequestStatus] = mapped_column(SAEnum(FriendRequestStatus), default=FriendRequestStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sender: Mapped["User"] = relationship(back_populates="sent_requests", foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship(back_populates="received_requests", foreign_keys=[receiver_id])


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user_a: Mapped["User"] = relationship(back_populates="friendships_a", foreign_keys=[user_a_id])
    user_b: Mapped["User"] = relationship(back_populates="friendships_b", foreign_keys=[user_b_id])


class UserBan(Base):
    __tablename__ = "user_bans"
    __table_args__ = (UniqueConstraint("banner_id", "banned_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    banner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    banned_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    banner: Mapped["User"] = relationship(back_populates="bans_issued", foreign_keys=[banner_id])
    banned: Mapped["User"] = relationship(back_populates="bans_received", foreign_keys=[banned_id])


class PersonalChat(Base):
    __tablename__ = "personal_chats"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user_a: Mapped["User"] = relationship(foreign_keys=[user_a_id])
    user_b: Mapped["User"] = relationship(foreign_keys=[user_b_id])
    messages: Mapped[list["Message"]] = relationship(back_populates="personal_chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True)
    personal_chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personal_chats.id", ondelete="CASCADE"), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    reply_to_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    author: Mapped["User"] = relationship(back_populates="messages")
    room: Mapped["Room"] = relationship(back_populates="messages")
    personal_chat: Mapped["PersonalChat"] = relationship(back_populates="messages")
    reply_to: Mapped["Message"] = relationship(remote_side="Message.id", foreign_keys=[reply_to_id])
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    read_receipts: Mapped[list["MessageRead"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127))
    file_size: Mapped[int] = mapped_column(BigInteger)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    is_image: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message"] = relationship(back_populates="attachments")
    uploader: Mapped["User"] = relationship(back_populates="attachments")


class MessageRead(Base):
    __tablename__ = "message_reads"
    __table_args__ = (UniqueConstraint("message_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message"] = relationship(back_populates="read_receipts")
