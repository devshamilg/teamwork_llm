import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from auth import (
    UserManager,
    UserRead,
    current_active_user,
    get_jwt_strategy,
    get_user_manager,
)
from database.engine import async_session_maker, get_async_session
from database.tables import Message, Room, RoomInvitation, RoomMember, User
from schemas import InviteMember, MessageCreate, RoomCreate, UserUpdate
from utils.connection_manager import manager

router = APIRouter(prefix="/api", tags=["api"])


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    user_manager: UserManager = Depends(get_user_manager),
) -> User:
    raw_token = token
    auth_header = websocket.headers.get("authorization")
    if not raw_token and auth_header and auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()

    if not raw_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    strategy = get_jwt_strategy()
    user = await strategy.read_token(raw_token, user_manager)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


async def get_room_with_access(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> Room:
    stmt = (
        select(Room)
        .outerjoin(RoomMember, RoomMember.room_id == Room.id)
        .outerjoin(RoomInvitation, RoomInvitation.room_id == Room.id)
        .where(
            Room.id == room_id,
            or_(
                Room.created_by == user_id,
                RoomMember.user_id == user_id,
                RoomInvitation.user_id == user_id,
            ),
        )
    )
    result = await session.execute(stmt)
    room = result.scalars().first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found or you do not have access.",
        )
    return room


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(current_active_user)):
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.bio is not None:
        user.bio = payload.bio.strip() if payload.bio.strip() else None

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/notifications")
async def list_notifications(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    stmt = (
        select(RoomInvitation)
        .options(
            joinedload(RoomInvitation.room),
            joinedload(RoomInvitation.inviter),
        )
        .where(RoomInvitation.user_id == user.id)
        .order_by(RoomInvitation.created_at.desc())
    )
    result = await session.execute(stmt)
    invitations = result.scalars().all()
    return [
        {
            "id": str(inv.id),
            "type": "invitation",
            "room_id": str(inv.room_id),
            "room_name": inv.room.name if inv.room else "Room",
            "invited_by": inv.inviter.display_name if inv.inviter else "Someone",
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in invitations
    ]


@router.post("/rooms/{room_id}/invitations", status_code=201)
async def invite_room_member(
    room_id: uuid.UUID,
    payload: InviteMember,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    room = await get_room_with_access(room_id, user.id, session)

    ident = payload.identifier.strip()
    target_stmt = select(User).where(
        or_(
            User.email == ident,
            User.username == ident,
        )
    )
    res = await session.execute(target_stmt)
    target_user = res.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{ident}' not found.",
        )

    if target_user.id == room.created_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is the room owner.",
        )

    # Check if already a member or invited
    existing_mem_stmt = select(RoomMember).where(
        RoomMember.room_id == room_id,
        RoomMember.user_id == target_user.id,
    )
    existing_mem_res = await session.execute(existing_mem_stmt)
    if existing_mem_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{target_user.display_name} is already a member of this room.",
        )

    invitation = RoomInvitation(
        room_id=room_id,
        user_id=target_user.id,
        invited_by=user.id,
    )
    membership = RoomMember(
        room_id=room_id,
        user_id=target_user.id,
        role="member",
    )
    session.add(invitation)
    session.add(membership)
    await session.commit()

    return {
        "message": f"Successfully invited {target_user.display_name} (@{target_user.username})",
        "user_id": str(target_user.id),
        "username": target_user.username,
        "display_name": target_user.display_name,
    }


@router.get("/rooms")
async def list_user_rooms(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    stmt = (
        select(Room)
        .outerjoin(RoomMember, RoomMember.room_id == Room.id)
        .outerjoin(RoomInvitation, RoomInvitation.room_id == Room.id)
        .where(
            or_(
                Room.created_by == user.id,
                RoomMember.user_id == user.id,
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
    await session.flush()

    # Automatically add creator as owner in room_members
    owner_membership = RoomMember(
        room_id=room.id,
        user_id=user.id,
        role="owner",
    )
    session.add(owner_membership)
    await session.commit()
    await session.refresh(room)
    return {
        "id": str(room.id),
        "name": room.name,
        "description": room.description,
        "visibility": room.visibility,
    }


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    room = await get_room_with_access(room_id, user.id, session)
    return {
        "id": str(room.id),
        "name": room.name,
        "description": room.description,
        "visibility": room.visibility,
        "created_by": str(room.created_by),
        "is_owner": room.created_by == user.id,
    }


@router.get("/rooms/{room_id}/messages")
async def get_room_messages(
    room_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await get_room_with_access(room_id, user.id, session)

    stmt = (
        select(Message)
        .options(joinedload(Message.sender))
        .where(
            Message.room_id == room_id,
            Message.is_deleted.is_(False),
        )
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "room_id": str(m.room_id),
            "sender_id": str(m.sender_id) if m.sender_id else None,
            "sender_type": m.sender_type,
            "sender_name": m.sender.display_name if m.sender else (
                "Assistant" if m.sender_type == "assistant" else "System"
            ),
            "sender_username": m.sender.username if m.sender else None,
            "content": m.content,
            "message_type": m.message_type,
            "reply_to_message_id": str(m.reply_to_message_id) if m.reply_to_message_id else None,
            "is_edited": m.is_edited,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/rooms/{room_id}/messages", status_code=201)
async def create_room_message(
    room_id: uuid.UUID,
    payload: MessageCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await get_room_with_access(room_id, user.id, session)

    clean_content = payload.content.strip()
    if not clean_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty.",
        )

    message = Message(
        room_id=room_id,
        sender_id=user.id,
        sender_type="user",
        content=clean_content,
        message_type=payload.message_type,
        reply_to_message_id=payload.reply_to_message_id,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    response_payload = {
        "id": str(message.id),
        "room_id": str(message.room_id),
        "sender_id": str(message.sender_id),
        "sender_type": message.sender_type,
        "sender_name": user.display_name,
        "sender_username": user.username,
        "content": message.content,
        "message_type": message.message_type,
        "reply_to_message_id": str(message.reply_to_message_id) if message.reply_to_message_id else None,
        "is_edited": message.is_edited,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }
    await manager.broadcast(room_id, response_payload)
    return response_payload


@router.websocket("/ws/rooms/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user_ws),
):
    # Verify user access to the room
    async with async_session_maker() as session:
        try:
            await get_room_with_access(room_id, current_user.id, session)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(room_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            if isinstance(data, str):
                content = data.strip()
                msg_type = "text"
                reply_to_id = None
            elif isinstance(data, dict):
                content = str(data.get("content", "")).strip()
                msg_type = str(data.get("message_type", "text"))
                reply_to_id = data.get("reply_to_message_id")
            else:
                continue

            if not content:
                continue

            async with async_session_maker() as session:
                parsed_reply_to = uuid.UUID(str(reply_to_id)) if reply_to_id else None
                message = Message(
                    room_id=room_id,
                    sender_id=current_user.id,
                    sender_type="user",
                    content=content,
                    message_type=msg_type,
                    reply_to_message_id=parsed_reply_to,
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)

                payload = {
                    "id": str(message.id),
                    "room_id": str(message.room_id),
                    "sender_id": str(message.sender_id),
                    "sender_type": message.sender_type,
                    "sender_name": current_user.display_name,
                    "sender_username": current_user.username,
                    "content": message.content,
                    "message_type": message.message_type,
                    "reply_to_message_id": str(message.reply_to_message_id) if message.reply_to_message_id else None,
                    "is_edited": message.is_edited,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                }

            await manager.broadcast(room_id, payload)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
    except Exception:
        manager.disconnect(room_id, websocket)



