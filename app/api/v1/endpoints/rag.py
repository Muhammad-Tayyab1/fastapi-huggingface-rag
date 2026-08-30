import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.rate_limit import client_ip, rate_limiter
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSearchRequest, RAGSearchResponse
from app.services import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RAGSearchResponse)
async def search(
    data: RAGSearchRequest, user: CurrentUser, session: SessionDep, request: Request
) -> RAGSearchResponse:
    await _limit_rag(request, str(user.id))
    return await rag_service.search_response(session, user.id, data)


@router.post("/query", response_model=RAGQueryResponse)
async def query(
    data: RAGQueryRequest, user: CurrentUser, session: SessionDep, request: Request
) -> RAGQueryResponse:
    await _limit_rag(request, str(user.id))
    return await rag_service.query(session, user.id, data)


@router.post("/query/stream", response_class=StreamingResponse)
async def stream_query(
    data: RAGQueryRequest, user: CurrentUser, session: SessionDep, request: Request
) -> StreamingResponse:
    await _limit_rag(request, str(user.id))
    prepared = await rag_service.prepare_query(session, user.id, data)

    async def events() -> AsyncIterator[str]:
        source_data = [source.model_dump(mode="json") for source in prepared.sources]
        yield f"event: sources\ndata: {json.dumps(source_data)}\n\n"
        async for token in rag_service.stream_prepared(session, prepared):
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
        done = {"conversation_id": str(prepared.conversation.id)}
        yield f"event: done\ndata: {json.dumps(done)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _limit_rag(request: Request, user_id: str) -> None:
    await rate_limiter.check(
        action="rag",
        identities=[client_ip(request), user_id],
        limit=settings.rag_rate_limit_per_min,
        window_seconds=60,
    )
