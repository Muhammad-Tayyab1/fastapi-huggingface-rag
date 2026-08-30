from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models.document import Document, DocumentChunk
from app.repositories.chunks import ChunkRepository


class EmptyResult:
    def all(self):
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def exec(self, statement):
        self.statement = statement
        return EmptyResult()


async def test_similarity_search_enforces_ownership_and_ready_documents() -> None:
    session = CapturingSession()
    user_id = uuid4()
    document_id = uuid4()
    results = await ChunkRepository(session).similarity_search(
        user_id=user_id,
        query_embedding=[0.1] * 1024,
        document_ids=[document_id],
        top_k=5,
        min_score=0.7,
    )
    assert results == []
    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "document_chunks.user_id" in sql
    assert "documents.user_id" in sql
    assert "documents.status" in sql
    assert "document_chunks.document_id IN" in sql
    assert "<=>" in sql


def test_retrieval_models_keep_separate_owner_keys() -> None:
    assert "user_id" in Document.__table__.c
    assert "user_id" in DocumentChunk.__table__.c
