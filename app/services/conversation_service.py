from uuid import UUID

from fastapi import status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import AppError
from app.models.conversation import Conversation, Message
from app.repositories.conversations import ConversationRepository


async def owned_conversation(
    session: AsyncSession, conversation_id: UUID, user_id: UUID
) -> Conversation:
    conversation = await ConversationRepository(session).owned(conversation_id, user_id)
    if not conversation:
        raise AppError(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


async def get_or_create(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID | None,
    question: str,
) -> Conversation:
    if conversation_id:
        return await owned_conversation(session, conversation_id, user_id)
    title = question.strip().replace("\n", " ")[:80] or "New conversation"
    return await ConversationRepository(session).create(Conversation(user_id=user_id, title=title))


async def history(
    session: AsyncSession, conversation: Conversation, limit: int = 10
) -> list[Message]:
    return await ConversationRepository(session).messages(conversation.id, limit)
