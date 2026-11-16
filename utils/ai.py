import os
import uuid
from typing import Optional, Union

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.engine import async_session_maker
from database.tables import Message
from utils.connection_manager import manager
from utils.celery_app import celery_app

load_dotenv()


def get_openai_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)


async def async_process_ai_mention(
    room_id: Union[uuid.UUID, str],
    prompt: str,
    user_message_id: Optional[Union[uuid.UUID, str]] = None,
) -> Optional[dict]:
    """Background task to query OpenAI and broadcast reply to the room."""
    room_uuid = uuid.UUID(str(room_id))
    user_msg_uuid = uuid.UUID(str(user_message_id)) if user_message_id else None

    # Default prompt if user only typed "@AI" without a question
    clean_prompt = prompt.strip() if prompt and prompt.strip() else "Hello! How can I help you today?"

    try:
        # 1. Fetch recent room messages for context
        async with async_session_maker() as session:
            stmt = (
                select(Message)
                .options(joinedload(Message.sender))
                .where(Message.room_id == room_uuid, Message.is_deleted.is_(False))
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            recent_messages = list(reversed(result.scalars().all()))

        # 2. Build OpenAI chat messages history
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant collaborating in a team chat room. "
                    "Provide clear, concise, and helpful answers, do not use markdown in responses."
                ),
            }
        ]

        for m in recent_messages:
            if m.sender_type == "assistant":
                messages.append({"role": "assistant", "content": m.content})
            else:
                sender_name = m.sender.display_name if m.sender else "User"
                messages.append({
                    "role": "user",
                    "content": f"{sender_name}: {m.content}",
                })

        # Add the latest user prompt
        messages.append({"role": "user", "content": clean_prompt})

        # 3. Call OpenAI Chat Completions API with fallback to gpt-4o-mini
        client = get_openai_client()
        configured_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

        try:
            response = await client.chat.completions.create(
                model=configured_model,
                messages=messages,
            )
            ai_reply = response.choices[0].message.content or ""
            ai_reply = ai_reply.strip()
        except Exception as model_err:
            print(f"Warning: Model '{configured_model}' failed: {model_err}. Falling back to 'gpt-4o-mini'...")
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
            ai_reply = response.choices[0].message.content or ""
            ai_reply = ai_reply.strip()

        if not ai_reply:
            return None

        # 4. Save the AI message to PostgreSQL
        async with async_session_maker() as session:
            ai_msg = Message(
                room_id=room_uuid,
                sender_id=None,
                sender_type="assistant",
                content=ai_reply,
                message_type="text",
                reply_to_message_id=user_msg_uuid,
            )
            session.add(ai_msg)
            await session.commit()
            await session.refresh(ai_msg)

            payload = {
                "id": str(ai_msg.id),
                "room_id": str(ai_msg.room_id),
                "sender_id": None,
                "sender_type": "assistant",
                "sender_name": "AI Assistant",
                "sender_username": None,
                "content": ai_msg.content,
                "message_type": ai_msg.message_type,
                "reply_to_message_id": str(ai_msg.reply_to_message_id) if ai_msg.reply_to_message_id else None,
                "is_edited": False,
                "created_at": ai_msg.created_at.isoformat(),
            }

        # 5. Broadcast directly to all users in the room via WebSocket
        await manager.broadcast(room_uuid, payload)
        return payload

    except Exception as exc:
        print(f"Error generating OpenAI response: {exc}")
        # Broadcast visible error message to chat so users are not left wondering why AI did not respond
        try:
            async with async_session_maker() as session:
                err_content = f"⚠️ AI Assistant error: {exc}"
                err_msg = Message(
                    room_id=room_uuid,
                    sender_id=None,
                    sender_type="assistant",
                    content=err_content,
                    message_type="text",
                    reply_to_message_id=user_msg_uuid,
                )
                session.add(err_msg)
                await session.commit()
                await session.refresh(err_msg)

                err_payload = {
                    "id": str(err_msg.id),
                    "room_id": str(err_msg.room_id),
                    "sender_id": None,
                    "sender_type": "assistant",
                    "sender_name": "AI Assistant",
                    "sender_username": None,
                    "content": err_msg.content,
                    "message_type": err_msg.message_type,
                    "reply_to_message_id": str(err_msg.reply_to_message_id) if err_msg.reply_to_message_id else None,
                    "is_edited": False,
                    "created_at": err_msg.created_at.isoformat(),
                }
            await manager.broadcast(room_uuid, err_payload)
        except Exception as broadcast_err:
            print(f"Error broadcasting failure payload: {broadcast_err}")
        return None

