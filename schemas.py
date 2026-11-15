import uuid
from typing import Optional

from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: str = "text"
    reply_to_message_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = None


class InviteMember(BaseModel):
    identifier: str = Field(..., min_length=1)

