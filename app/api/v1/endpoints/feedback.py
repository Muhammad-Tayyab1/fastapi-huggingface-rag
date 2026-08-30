from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.exceptions import AppError
from app.models.conversation import Message
from app.repositories.feedback import FeedbackRepository
from app.schemas.feedback import FeedbackRead, FeedbackSummary, FeedbackUpsert

router = APIRouter(prefix="/feedback", tags=["feedback"])


async def owned_assistant_message(
    repository: FeedbackRepository, message_id: UUID, user_id: UUID
) -> Message:
    message = await repository.owned_assistant_message(message_id, user_id)
    if not message:
        raise AppError(status.HTTP_404_NOT_FOUND, "Assistant message not found")
    return message


@router.put("/messages/{message_id}", response_model=FeedbackRead)
async def upsert_feedback(
    message_id: UUID,
    data: FeedbackUpsert,
    user: CurrentUser,
    session: SessionDep,
) -> FeedbackRead:
    repository = FeedbackRepository(session)
    await owned_assistant_message(repository, message_id, user.id)
    feedback = await repository.upsert(message_id, user.id, data.rating, data.comment)
    return FeedbackRead.model_validate(feedback)


@router.get("/messages/{message_id}", response_model=FeedbackRead)
async def get_feedback(message_id: UUID, user: CurrentUser, session: SessionDep) -> FeedbackRead:
    repository = FeedbackRepository(session)
    await owned_assistant_message(repository, message_id, user.id)
    feedback = await repository.owned(message_id, user.id)
    if not feedback:
        raise AppError(status.HTTP_404_NOT_FOUND, "Feedback not found")
    return FeedbackRead.model_validate(feedback)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(message_id: UUID, user: CurrentUser, session: SessionDep) -> Response:
    repository = FeedbackRepository(session)
    await owned_assistant_message(repository, message_id, user.id)
    feedback = await repository.owned(message_id, user.id)
    if not feedback:
        raise AppError(status.HTTP_404_NOT_FOUND, "Feedback not found")
    await repository.delete(feedback)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/summary", response_model=FeedbackSummary)
async def feedback_summary(user: CurrentUser, session: SessionDep) -> FeedbackSummary:
    total, positive = await FeedbackRepository(session).summary(user.id)
    return FeedbackSummary(
        total=total,
        positive=positive,
        negative=total - positive,
        positive_rate=round(positive / total, 4) if total else None,
    )
