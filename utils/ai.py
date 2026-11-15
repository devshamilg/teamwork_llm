# services/ai.py
import asyncio
import os
import uuid
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from google import genai

from database.engine import async_session_maker
from database.tables import Message
from utils.connection_manager import manager

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


async def process_ai_mention(room_id: uuid.UUID, prompt: str, user_message_id: uuid.UUID | None = None):
    """Background task to query AI and broadcast its reply to the room."""
    try:
        # 1. Fetch recent room messages for context
        async with async_session_maker() as session:
            stmt = (
                select(Message)
                .options(joinedload(Message.sender))
                .where(Message.room_id == room_id, Message.is_deleted.is_(False))
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            recent_messages = list(reversed(result.scalars().all()))

        # 2. Build conversation history for the model
        context = "\n".join(
            f"{m.sender.display_name if m.sender else 'Assistant'}: {m.content}"
            for m in recent_messages
        )

        full_prompt = (
            f"You are a helpful AI assistant collaborating in a team chat room.\n"
            f"Recent conversation:\n{context}\n\n"
            f"Please respond directly to the question: {prompt}"
        )

        # 3. Call the LLM in an async executor thread
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
            ),
        )
        ai_reply = response.text.strip()

        # 4. Save the AI message to PostgreSQL
        async with async_session_maker() as session:
            ai_msg = Message(
                room_id=room_id,
                sender_id=None,
                sender_type="assistant",
                content=ai_reply,
                message_type="text",
                reply_to_message_id=user_message_id,
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

        # 5. Broadcast to all users in the room
        await manager.broadcast(room_id, payload)

    except Exception as exc:
        print(f"Error generating AI response: {exc}")