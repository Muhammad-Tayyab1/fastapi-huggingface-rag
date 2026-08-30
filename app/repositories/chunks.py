from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, literal_column
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    document_name: str
    score: float


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _ownership_filters(user_id: UUID):
        return (
            DocumentChunk.user_id == user_id,
            Document.user_id == user_id,
            Document.status == "ready",
        )

    async def similarity_search(
        self,
        *,
        user_id: UUID,
        query_text: str,
        query_embedding: list[float],
        document_ids: list[UUID] | None,
        top_k: int,
        min_score: float,
    ) -> list[RetrievedChunk]:
        candidate_limit = top_k * settings.hybrid_candidate_multiplier
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        semantic = (
            select(DocumentChunk, Document.name, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                *self._ownership_filters(user_id),
                DocumentChunk.embedding.is_not(None),
                distance <= 1 - min_score,
            )
            .order_by(distance)
            .limit(candidate_limit if settings.retrieval_mode == "hybrid" else top_k)
        )
        if document_ids is not None:
            semantic = semantic.where(DocumentChunk.document_id.in_(document_ids))
        semantic_rows = list((await self.session.exec(semantic)).all())
        if settings.retrieval_mode == "semantic":
            return [
                RetrievedChunk(
                    chunk=chunk,
                    document_name=name,
                    score=max(0.0, 1.0 - float(raw_distance)),
                )
                for chunk, name, raw_distance in semantic_rows
            ]

        configuration = literal_column("'english'")
        search_vector = func.to_tsvector(configuration, DocumentChunk.content)
        search_query = func.websearch_to_tsquery(configuration, query_text)
        text_rank = func.ts_rank_cd(search_vector, search_query)
        lexical = (
            select(DocumentChunk, Document.name, text_rank.label("text_rank"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                *self._ownership_filters(user_id),
                search_vector.op("@@")(search_query),
            )
            .order_by(text_rank.desc())
            .limit(candidate_limit)
        )
        if document_ids is not None:
            lexical = lexical.where(DocumentChunk.document_id.in_(document_ids))
        lexical_rows = list((await self.session.exec(lexical)).all())
        return self._fuse(semantic_rows, lexical_rows, top_k)

    @staticmethod
    def _fuse(semantic_rows: list[tuple], lexical_rows: list[tuple], top_k: int):
        candidates: dict[UUID, tuple[DocumentChunk, str]] = {}
        scores: dict[UUID, float] = {}
        k = settings.hybrid_rrf_k
        semantic_weight = settings.hybrid_semantic_weight
        for rank, (chunk, name, _) in enumerate(semantic_rows, start=1):
            candidates[chunk.id] = (chunk, name)
            scores[chunk.id] = scores.get(chunk.id, 0) + semantic_weight / (k + rank)
        for rank, (chunk, name, _) in enumerate(lexical_rows, start=1):
            candidates[chunk.id] = (chunk, name)
            scores[chunk.id] = scores.get(chunk.id, 0) + (1 - semantic_weight) / (k + rank)
        ranked = sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]
        return [
            RetrievedChunk(
                chunk=candidates[chunk_id][0],
                document_name=candidates[chunk_id][1],
                score=round(scores[chunk_id] * (k + 1), 6),
            )
            for chunk_id in ranked
        ]
