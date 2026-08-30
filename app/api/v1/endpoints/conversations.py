from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.models.conversation import Conversation
from app.repositories.conversations import ConversationRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    MessageRead,
)
from app.services.conversation_service import owned_conversation

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate, user: CurrentUser, session: SessionDep
) -> ConversationRead:
    conversation = Conversation(user_id=user.id, title=data.title or "New conversation")
    conversation = await ConversationRepository(session).create(conversation)
    return ConversationRead.model_validate(conversation)


@router.get("/", response_model=list[ConversationRead])
async def list_conversations(
    user: CurrentUser,
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ConversationRead]:
    conversations = await ConversationRepository(session).list_owned(user.id, offset, limit)
    return [ConversationRead.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID, user: CurrentUser, session: SessionDep
) -> ConversationDetail:
    conversation = await owned_conversation(session, conversation_id, user.id)
    messages = await ConversationRepository(session).messages(conversation.id)
    return ConversationDetail(
        **ConversationRead.model_validate(conversation).model_dump(),
        messages=[MessageRead.model_validate(message) for message in messages],
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MessageRead]:
    conversation = await owned_conversation(session, conversation_id, user.id)
    messages = await ConversationRepository(session).messages(conversation.id, limit)
    return [MessageRead.model_validate(message) for message in messages]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID, user: CurrentUser, session: SessionDep
) -> Response:
    conversation = await owned_conversation(session, conversation_id, user.id)
    await ConversationRepository(session).delete(conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
