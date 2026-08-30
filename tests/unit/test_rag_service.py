from uuid import uuid4

from app.models.conversation import Conversation
from app.models.document import DocumentChunk
from app.repositories.chunks import RetrievedChunk
from app.schemas.rag import RAGQueryRequest
from app.services import rag_service


class FakeEmbedder:
    async def embed_query(self, question: str) -> list[float]:
        assert question
        return [1.0] + [0.0] * 1023


class FakeLLM:
    def __init__(self) -> None:
        self.context = ""

    async def answer(self, question: str, context: str, history=None) -> str:
        self.context = context
        return f"Grounded answer for {question}"

    async def stream_answer(self, question: str, context: str, history=None):
        yield "Grounded "
        yield "answer"


async def mock_conversation_dependencies(monkeypatch):
    conversation = Conversation(id=uuid4(), user_id=uuid4(), title="Test")

    async def get_or_create(*_args, **_kwargs):
        return conversation

    async def history(*_args, **_kwargs):
        return []

    async def save_exchange(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.conversation_service.get_or_create", get_or_create)
    monkeypatch.setattr("app.services.conversation_service.history", history)
    monkeypatch.setattr(
        "app.repositories.conversations.ConversationRepository.save_exchange", save_exchange
    )
    return conversation


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
    conversation = await mock_conversation_dependencies(monkeypatch)
    llm = FakeLLM()
    response = await rag_service.query(
        object(),
        uuid4(),
        RAGQueryRequest(question="When can I cancel?"),
        embedding_service=FakeEmbedder(),
        llm_service=llm,
    )
    assert response.grounded is True
    assert response.sources[0].document_name == "policy.pdf"
    assert response.sources[0].page_number == 2
    assert "[Source 1: policy.pdf, page 2]" in llm.context
    assert response.conversation_id == conversation.id


async def test_query_uses_safe_no_context_response(monkeypatch) -> None:
    async def fake_search(*_args, **_kwargs):
        return []

    monkeypatch.setattr("app.repositories.chunks.ChunkRepository.similarity_search", fake_search)
    await mock_conversation_dependencies(monkeypatch)
    response = await rag_service.query(
        object(),
        uuid4(),
        RAGQueryRequest(question="Unknown question"),
        embedding_service=FakeEmbedder(),
        llm_service=FakeLLM(),
    )
    assert response.grounded is False
    assert response.sources == []
    assert response.answer == rag_service.NO_CONTEXT_ANSWER


async def test_search_falls_back_when_optional_reranking_fails(monkeypatch) -> None:
    candidates = [retrieved("first"), retrieved("second"), retrieved("third")]
    captured = {}

    async def fake_search(*_args, **kwargs):
        captured.update(kwargs)
        return candidates

    class BrokenReranker:
        async def rerank(self, *_args, **_kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.repositories.chunks.ChunkRepository.similarity_search", fake_search)
    monkeypatch.setattr(rag_service.settings, "reranking_enabled", True)
    monkeypatch.setattr(rag_service.settings, "rerank_candidate_multiplier", 3)
    monkeypatch.setattr(rag_service.settings, "reranker_fail_open", True)

    results, _ = await rag_service.search(
        object(),
        uuid4(),
        RAGQueryRequest(question="question", top_k=2),
        embedding_service=FakeEmbedder(),
        reranking_service=BrokenReranker(),
    )

    assert captured["top_k"] == 6
    assert results == candidates[:2]


async def test_stream_persists_only_the_completed_answer(monkeypatch) -> None:
    conversation = Conversation(id=uuid4(), user_id=uuid4(), title="Stream")
    prepared = rag_service.PreparedQuery(
        request=RAGQueryRequest(question="Stream this"),
        conversation=conversation,
        history=[],
        results=[retrieved()],
        sources=[],
    )
    saved = {}

    async def save_exchange(_self, _conversation, question, answer, sources):
        saved.update(question=question, answer=answer, sources=sources)

    monkeypatch.setattr(
        "app.repositories.conversations.ConversationRepository.save_exchange", save_exchange
    )
    tokens = [
        token
        async for token in rag_service.stream_prepared(object(), prepared, llm_service=FakeLLM())
    ]
    assert tokens == ["Grounded ", "answer"]
    assert saved["answer"] == "Grounded answer"
