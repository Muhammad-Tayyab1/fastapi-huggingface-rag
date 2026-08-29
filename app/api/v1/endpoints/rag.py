from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.rag import RAGQueryResponse, RAGSearchRequest, RAGSearchResponse
from app.services import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RAGSearchResponse)
async def search(
    request: RAGSearchRequest, user: CurrentUser, session: SessionDep
) -> RAGSearchResponse:
    return await rag_service.search_response(session, user.id, request)


@router.post("/query", response_model=RAGQueryResponse)
async def query(
    request: RAGSearchRequest, user: CurrentUser, session: SessionDep
) -> RAGQueryResponse:
    return await rag_service.query(session, user.id, request)
