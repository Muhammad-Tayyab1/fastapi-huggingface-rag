from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.repositories.chunks import ChunkRepository, RetrievedChunk
from app.schemas.rag import RAGQueryResponse, RAGSearchRequest, RAGSearchResponse, RAGSource
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

NO_CONTEXT_ANSWER = (
    "The provided documents do not contain enough information to answer this question."
)


def _source(result: RetrievedChunk) -> RAGSource:
    return RAGSource(
        chunk_id=result.chunk.id,
        document_id=result.chunk.document_id,
        document_name=result.document_name,
        page_number=result.chunk.page_number,
        score=round(result.score, 6),
        excerpt=result.chunk.content[:800],
    )


def build_context(results: list[RetrievedChunk]) -> str:
    sections: list[str] = []
    length = 0
    for number, result in enumerate(results, start=1):
        page = f", page {result.chunk.page_number}" if result.chunk.page_number else ""
        section = f"[Source {number}: {result.document_name}{page}]\n{result.chunk.content}"
        remaining = settings.rag_max_context_chars - length
        if remaining <= 0:
            break
        section = section[:remaining]
        sections.append(section)
        length += len(section) + 2
    return "\n\n".join(sections)


async def search(
    session: AsyncSession,
    user_id: UUID,
    request: RAGSearchRequest,
    embedding_service: EmbeddingService | None = None,
) -> tuple[list[RetrievedChunk], list[RAGSource]]:
    embedder = embedding_service or EmbeddingService()
    query_embedding = await embedder.embed_query(request.question)
    results = await ChunkRepository(session).similarity_search(
        user_id=user_id,
        query_embedding=query_embedding,
        document_ids=request.document_ids,
        top_k=request.top_k or settings.retrieval_top_k,
        min_score=request.min_score
        if request.min_score is not None
        else settings.retrieval_min_score,
    )
    return results, [_source(result) for result in results]


async def search_response(
    session: AsyncSession, user_id: UUID, request: RAGSearchRequest
) -> RAGSearchResponse:
    _, sources = await search(session, user_id, request)
    return RAGSearchResponse(question=request.question, sources=sources)


async def query(
    session: AsyncSession,
    user_id: UUID,
    request: RAGSearchRequest,
    embedding_service: EmbeddingService | None = None,
    llm_service: LLMService | None = None,
) -> RAGQueryResponse:
    results, sources = await search(session, user_id, request, embedding_service)
    if not results:
        return RAGQueryResponse(
            question=request.question,
            answer=NO_CONTEXT_ANSWER,
            sources=[],
            grounded=False,
        )
    generator = llm_service or LLMService()
    answer = await generator.answer(request.question, build_context(results))
    return RAGQueryResponse(
        question=request.question,
        answer=answer,
        sources=sources,
        grounded=True,
    )
