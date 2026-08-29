import math

import pytest
from huggingface_hub.errors import InferenceTimeoutError

from app.services.embedding_service import EmbeddingService


class FakeClient:
    def __init__(self, vectors: list[list[float]], failures: int = 0) -> None:
        self.vectors = vectors
        self.failures = failures
        self.calls: list[list[str]] = []
        self.returned = 0

    async def feature_extraction(self, texts, **_kwargs):
        self.calls.append(texts)
        if self.failures:
            self.failures -= 1
            raise InferenceTimeoutError("timed out")
        result = self.vectors[self.returned : self.returned + len(texts)]
        self.returned += len(result)
        return result


async def no_sleep(_: float) -> None:
    return None


async def test_embeddings_are_batched_and_normalized() -> None:
    client = FakeClient([[3, 4, 0], [0, 2, 0], [1, 2, 2]])
    service = EmbeddingService(client, dimension=3, batch_size=2, sleep=no_sleep)
    vectors = await service.embed_documents(["one", "two", "three"])
    assert [len(call) for call in client.calls] == [2, 1]
    assert len(vectors) == 3
    assert all(
        math.isclose(math.sqrt(sum(value * value for value in vector)), 1) for vector in vectors
    )


async def test_embedding_request_retries_timeout() -> None:
    client = FakeClient([[1, 0, 0]], failures=1)
    service = EmbeddingService(
        client,
        dimension=3,
        batch_size=1,
        max_retries=2,
        sleep=no_sleep,
    )
    assert await service.embed_documents(["one"]) == [[1, 0, 0]]
    assert len(client.calls) == 2


async def test_embedding_dimension_mismatch_is_rejected() -> None:
    service = EmbeddingService(FakeClient([[1, 0]]), dimension=3, sleep=no_sleep)
    with pytest.raises(ValueError, match="dimension mismatch"):
        await service.embed_documents(["one"])


async def test_embedding_count_mismatch_is_rejected() -> None:
    service = EmbeddingService(FakeClient([]), dimension=3, sleep=no_sleep)
    with pytest.raises(ValueError, match="count mismatch"):
        await service.embed_documents(["one"])
