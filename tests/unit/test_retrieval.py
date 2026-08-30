from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models.document import Document, DocumentChunk
from app.repositories.chunks import ChunkRepository


class EmptyResult:
    def all(self):
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statements = []

    async def exec(self, statement):
        self.statements.append(statement)
        return EmptyResult()


async def test_similarity_search_enforces_ownership_and_ready_documents() -> None:
    session = CapturingSession()
    user_id = uuid4()
    document_id = uuid4()
    results = await ChunkRepository(session).similarity_search(
        user_id=user_id,
        query_text="exact policy phrase",
        query_embedding=[0.1] * 1024,
        document_ids=[document_id],
        top_k=5,
        min_score=0.7,
    )
    assert results == []
    assert len(session.statements) == 2
    semantic_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    lexical_sql = str(session.statements[1].compile(dialect=postgresql.dialect()))
    for sql in (semantic_sql, lexical_sql):
        assert "document_chunks.user_id" in sql
        assert "documents.user_id" in sql
        assert "documents.status" in sql
        assert "document_chunks.document_id IN" in sql
    assert "<=>" in semantic_sql
    assert "@@" in lexical_sql
    assert "websearch_to_tsquery" in lexical_sql


def test_retrieval_models_keep_separate_owner_keys() -> None:
    assert "user_id" in Document.__table__.c
    assert "user_id" in DocumentChunk.__table__.c


def test_reciprocal_rank_fusion_rewards_results_from_both_paths() -> None:
    user_id = uuid4()
    semantic_only = DocumentChunk(
        document_id=uuid4(), user_id=user_id, content="semantic", chunk_index=0
    )
    overlap = DocumentChunk(document_id=uuid4(), user_id=user_id, content="overlap", chunk_index=0)
    lexical_only = DocumentChunk(
        document_id=uuid4(), user_id=user_id, content="lexical", chunk_index=0
    )

    results = ChunkRepository._fuse(
        [(semantic_only, "semantic.txt", 0.1), (overlap, "overlap.txt", 0.2)],
        [(overlap, "overlap.txt", 0.9), (lexical_only, "lexical.txt", 0.8)],
        top_k=3,
    )

    assert [result.chunk.content for result in results] == ["overlap", "semantic", "lexical"]
    assert all(0 < result.score <= 1 for result in results)
