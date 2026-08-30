from dataclasses import dataclass
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.document import Document, DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    document_name: str
    score: float


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def similarity_search(
        self,
        *,
        user_id: UUID,
        query_embedding: list[float],
        document_ids: list[UUID] | None,
        top_k: int,
        min_score: float,
    ) -> list[RetrievedChunk]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        statement = (
            select(DocumentChunk, Document.name, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                Document.user_id == user_id,
                Document.status == "ready",
                DocumentChunk.embedding.is_not(None),
                distance <= 1 - min_score,
            )
            .order_by(distance)
            .limit(top_k)
        )
        if document_ids is not None:
            statement = statement.where(DocumentChunk.document_id.in_(document_ids))
        result = await self.session.exec(statement)
        return [
            RetrievedChunk(
                chunk=chunk, document_name=name, score=max(0.0, 1.0 - float(raw_distance))
            )
            for chunk, name, raw_distance in result.all()
        ]
