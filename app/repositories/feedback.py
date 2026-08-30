from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.base import utcnow
from app.models.conversation import AnswerFeedback, Conversation, Message


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def owned_assistant_message(self, message_id: UUID, user_id: UUID) -> Message | None:
        result = await self.session.exec(
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.id == message_id,
                Message.role == "assistant",
                Conversation.user_id == user_id,
            )
        )
        return result.first()

    async def owned(self, message_id: UUID, user_id: UUID) -> AnswerFeedback | None:
        result = await self.session.exec(
            select(AnswerFeedback).where(
                AnswerFeedback.message_id == message_id,
                AnswerFeedback.user_id == user_id,
            )
        )
        return result.first()

    async def upsert(
        self, message_id: UUID, user_id: UUID, rating: str, comment: str | None
    ) -> AnswerFeedback:
        feedback = await self.owned(message_id, user_id)
        if feedback:
            feedback.rating = rating
            feedback.comment = comment
            feedback.updated_at = utcnow()
        else:
            feedback = AnswerFeedback(
                message_id=message_id,
                user_id=user_id,
                rating=rating,
                comment=comment,
            )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def delete(self, feedback: AnswerFeedback) -> None:
        await self.session.delete(feedback)
        await self.session.commit()

    async def summary(self, user_id: UUID) -> tuple[int, int]:
        result = await self.session.exec(
            select(
                func.count(AnswerFeedback.id),
                func.count(AnswerFeedback.id).filter(AnswerFeedback.rating == "up"),
            ).where(AnswerFeedback.user_id == user_id)
        )
        total, positive = result.one()
        return int(total), int(positive)
