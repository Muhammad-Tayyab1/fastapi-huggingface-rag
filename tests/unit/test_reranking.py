from uuid import uuid4

import pytest
from huggingface_hub.errors import InferenceTimeoutError

from app.models.document import DocumentChunk
from app.repositories.chunks import RetrievedChunk
from app.services.reranking_service import RerankingService


class FakeClient:
    def __init__(self, scores: list[float], failures: int = 0) -> None:
        self.scores = scores
        self.failures = failures
        self.calls = 0

    async def sentence_similarity(self, *_args, **_kwargs):
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise InferenceTimeoutError("timed out")
        return self.scores


async def no_sleep(_: float) -> None:
    return None


def candidate(content: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=DocumentChunk(document_id=uuid4(), user_id=uuid4(), content=content, chunk_index=0),
        document_name=f"{content}.txt",
        score=score,
    )


async def test_reranker_reorders_and_limits_candidates() -> None:
    service = RerankingService(FakeClient([-0.5, 0.9, 0.2]))

    results = await service.rerank(
        "question",
        [candidate("first", 0.9), candidate("second", 0.8), candidate("third", 0.7)],
        top_k=2,
    )

    assert [result.chunk.content for result in results] == ["second", "third"]
    assert [result.score for result in results] == [0.95, 0.6]


async def test_reranker_retries_provider_timeout() -> None:
    client = FakeClient([0.5], failures=1)
    service = RerankingService(client, max_retries=2, sleep=no_sleep)

    assert (await service.rerank("question", [candidate("answer", 0.5)], 1))[0].score == 0.75
    assert client.calls == 2


async def test_reranker_rejects_invalid_provider_response() -> None:
    service = RerankingService(FakeClient([]))

    with pytest.raises(ValueError, match="count mismatch"):
        await service.rerank("question", [candidate("answer", 0.5)], 1)
