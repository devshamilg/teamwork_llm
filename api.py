from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import UserRead, current_active_user
from database.engine import get_async_session
from database.tables import Room, RoomInvitation, User

router = APIRouter(prefix="/api", tags=["api"])


class RoomCreate(BaseModel):
    name: str
    description: Optional[str] = None


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(current_active_user)):
    return user


@router.get("/rooms")
async def list_user_rooms(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    stmt = (
        select(Room)
        .outerjoin(RoomInvitation, RoomInvitation.room_id == Room.id)
        .where(
            or_(
                Room.created_by == user.id,
                RoomInvitation.user_id == user.id,
            )
        )
        .distinct()
        .order_by(Room.created_at.desc())
    )
    result = await session.execute(stmt)
    rooms = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "visibility": r.visibility,
            "created_by": str(r.created_by),
        }
        for r in rooms
    ]


@router.post("/rooms", status_code=201)
async def create_room(
    payload: RoomCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    room = Room(
        name=payload.name,
        description=payload.description,
        created_by=user.id,
    )
    session.add(room)
    await session.commit()
    await session.refresh(room)
    return {
        "id": str(room.id),
        "name": room.name,
        "description": room.description,
        "visibility": room.visibility,
    }
