import sys
import uuid
import warnings
from datetime import datetime
from types import ModuleType
from typing import Any, List, Optional

warnings.filterwarnings("ignore", message="Valid config keys have changed in V2.*")
warnings.filterwarnings("ignore", message=".*inherit from .BaseModel. before generic classes.*")

# Fallback for passlib's legacy import of pkg_resources in Python 3.12+
try:
    import pkg_resources
except ImportError:
    sys.modules["pkg_resources"] = ModuleType("pkg_resources")

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseUserTable,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Ensure compatibility between fastapi-users-db-sqlalchemy mixin annotations and SQLAlchemy 2.0+
if hasattr(SQLAlchemyBaseUserTable, "__annotations__"):
    if not any("Mapped" in str(ann) for ann in SQLAlchemyBaseUserTable.__annotations__.values()):
        SQLAlchemyBaseUserTable.__annotations__ = {}
if hasattr(SQLAlchemyBaseUserTableUUID, "__annotations__"):
    if not any("Mapped" in str(ann) for ann in SQLAlchemyBaseUserTableUUID.__annotations__.values()):
        SQLAlchemyBaseUserTableUUID.__annotations__ = {}


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    Users table integrated with fastapi-users.
    Inherits UUID id, hashed_password, is_active, is_superuser, and is_verified
    from SQLAlchemyBaseUserTableUUID.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    rooms_created: Mapped[List["Room"]] = relationship(
        "Room",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    invitations_sent: Mapped[List["RoomInvitation"]] = relationship(
        "RoomInvitation",
        foreign_keys="RoomInvitation.invited_by",
        back_populates="inviter",
        cascade="all, delete-orphan",
    )
    invitations_received: Mapped[List["RoomInvitation"]] = relationship(
        "RoomInvitation",
        foreign_keys="RoomInvitation.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="sender",
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="private",
        server_default=text("'private'"),
    )
    max_members: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        server_default=text("50"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="rooms_created",
    )
    invitations: Mapped[List["RoomInvitation"]] = relationship(
        "RoomInvitation",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[List["RoomSummary"]] = relationship(
        "RoomSummary",
        back_populates="room",
        cascade="all, delete-orphan",
    )


class RoomInvitation(Base):
    __tablename__ = "room_invitations"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_invitations_room_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default=text("'member'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="invitations",
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="invitations_received",
    )
    inviter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invited_by],
        back_populates="invitations_sent",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('user', 'assistant', 'system')",
            name="ck_messages_sender_type",
        ),
        CheckConstraint(
            "message_type IN ('text', 'image', 'file', 'system')",
            name="ck_messages_message_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default=text("'text'"),
    )
    reply_to_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Note: Named 'metadata_' in Python to prevent collision with Declarative 'Base.metadata',
    # while the database column name is exactly 'metadata'.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_edited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="messages",
    )
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="messages",
    )
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message",
        remote_side=[id],
        backref="replies",
    )


class RoomSummary(Base):
    __tablename__ = "room_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    start_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    end_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    summary_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="conversation",
        server_default=text("'conversation'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="summaries",
    )
    start_message: Mapped[Optional["Message"]] = relationship(
        "Message",
        foreign_keys=[start_message_id],
    )
    end_message: Mapped[Optional["Message"]] = relationship(
        "Message",
        foreign_keys=[end_message_id],
    )


__all__ = [
    "Base",
    "User",
    "Room",
    "RoomInvitation",
    "Message",
    "RoomSummary",
]

