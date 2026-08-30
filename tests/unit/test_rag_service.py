from uuid import uuid4

from app.models.document import DocumentChunk
from app.repositories.chunks import RetrievedChunk
from app.schemas.rag import RAGSearchRequest
from app.services import rag_service


class FakeEmbedder:
    async def embed_query(self, question: str) -> list[float]:
        assert question
        return [1.0] + [0.0] * 1023


class FakeLLM:
    def __init__(self) -> None:
        self.context = ""

    async def answer(self, question: str, context: str) -> str:
        self.context = context
        return f"Grounded answer for {question}"


def retrieved(content: str = "The policy permits cancellation within 30 days.") -> RetrievedChunk:
    chunk = DocumentChunk(
        document_id=uuid4(),
        user_id=uuid4(),
        content=content,
        chunk_index=0,
        page_number=2,
        token_count=7,
    )
    return RetrievedChunk(chunk=chunk, document_name="policy.pdf", score=0.91)


async def test_query_returns_grounded_answer_and_citations(monkeypatch) -> None:
    async def fake_search(*_args, **_kwargs):
        return [retrieved()]

    monkeypatch.setattr("app.repositories.chunks.ChunkRepository.similarity_search", fake_search)
    llm = FakeLLM()
    response = await rag_service.query(
        object(),
        uuid4(),
        RAGSearchRequest(question="When can I cancel?"),
        embedding_service=FakeEmbedder(),
        llm_service=llm,
    )
    assert response.grounded is True
    assert response.sources[0].document_name == "policy.pdf"
    assert response.sources[0].page_number == 2
    assert "[Source 1: policy.pdf, page 2]" in llm.context


async def test_query_uses_safe_no_context_response(monkeypatch) -> None:
    async def fake_search(*_args, **_kwargs):
        return []

    monkeypatch.setattr("app.repositories.chunks.ChunkRepository.similarity_search", fake_search)
    response = await rag_service.query(
        object(),
        uuid4(),
        RAGSearchRequest(question="Unknown question"),
        embedding_service=FakeEmbedder(),
        llm_service=FakeLLM(),
    )
    assert response.grounded is False
    assert response.sources == []
    assert response.answer == rag_service.NO_CONTEXT_ANSWER
