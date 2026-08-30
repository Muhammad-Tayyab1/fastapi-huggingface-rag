from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.base import utcnow
from app.models.conversation import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def owned(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        result = await self.session.exec(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.first()

    async def list_owned(
        self, user_id: UUID, offset: int = 0, limit: int = 20
    ) -> list[Conversation]:
        result = await self.session.exec(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def create(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def messages(self, conversation_id: UUID, limit: int = 50) -> list[Message]:
        result = await self.session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def save_exchange(
        self,
        conversation: Conversation,
        question: str,
        answer: str,
        sources: list[dict],
    ) -> tuple[Message, Message]:
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=question,
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            sources=sources,
        )
        conversation.updated_at = utcnow()
        self.session.add(conversation)
        self.session.add(user_message)
        self.session.add(assistant_message)
        await self.session.commit()
        return user_message, assistant_message

    async def delete(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)
        await self.session.commit()
