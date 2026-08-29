import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, SessionDep
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSearchRequest, RAGSearchResponse
from app.services import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RAGSearchResponse)
async def search(
    request: RAGSearchRequest, user: CurrentUser, session: SessionDep
) -> RAGSearchResponse:
    return await rag_service.search_response(session, user.id, request)


@router.post("/query", response_model=RAGQueryResponse)
async def query(
    request: RAGQueryRequest, user: CurrentUser, session: SessionDep
) -> RAGQueryResponse:
    return await rag_service.query(session, user.id, request)


@router.post("/query/stream", response_class=StreamingResponse)
async def stream_query(
    request: RAGQueryRequest, user: CurrentUser, session: SessionDep
) -> StreamingResponse:
    prepared = await rag_service.prepare_query(session, user.id, request)

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
