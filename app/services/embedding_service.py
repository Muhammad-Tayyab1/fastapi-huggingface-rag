import asyncio
import math
from collections.abc import Awaitable, Callable
from typing import Any

from huggingface_hub import AsyncInferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.core.config import settings
from app.core.metrics import PROVIDER_REQUESTS

Sleep = Callable[[float], Awaitable[None]]


class EmbeddingService:
    def __init__(
        self,
        client: Any | None = None,
        *,
        dimension: int | None = None,
        batch_size: int | None = None,
        max_retries: int | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        token = settings.hf_token.get_secret_value()
        if client is None and not token:
            raise RuntimeError("HF_TOKEN is required for document embeddings")
        self.client = client or AsyncInferenceClient(
            provider=settings.hf_provider,
            api_key=token,
            timeout=settings.hf_timeout_seconds,
        )
        self.dimension = dimension or settings.embedding_dimension
        self.batch_size = batch_size or settings.hf_embedding_batch_size
        self.max_retries = max_retries or settings.hf_max_retries
        self.sleep = sleep

    async def _request(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.client.feature_extraction(
                    texts,
                    model=settings.hf_embedding_model,
                    normalize=True,
                    truncate=True,
                )
                values = result.tolist() if hasattr(result, "tolist") else result
                PROVIDER_REQUESTS.labels("embedding", "success").inc()
                return [[float(value) for value in vector] for vector in values]
            except (HfHubHTTPError, InferenceTimeoutError) as exc:
                PROVIDER_REQUESTS.labels("embedding", "error").inc()
                if attempt == self.max_retries:
                    raise RuntimeError("Hugging Face embedding request failed") from exc
                await self.sleep(2 ** (attempt - 1))
        raise RuntimeError("Hugging Face embedding request failed")

    def _validate_and_normalize(self, vectors: list[list[float]]) -> list[list[float]]:
        normalized: list[list[float]] = []
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimension}, received {len(vector)}"
                )
            magnitude = math.sqrt(sum(value * value for value in vector))
            if magnitude == 0 or not math.isfinite(magnitude):
                raise ValueError("Embedding vector has invalid magnitude")
            normalized.append([value / magnitude for value in vector])
        return normalized

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors = await self._request(batch)
            if len(vectors) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: expected {len(batch)}, received {len(vectors)}"
                )
            embeddings.extend(self._validate_and_normalize(vectors))
        return embeddings

    async def embed_query(self, question: str) -> list[float]:
        return (await self.embed_documents([question]))[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    return await EmbeddingService().embed_documents(texts)


async def embed_query(question: str) -> list[float]:
    return await EmbeddingService().embed_query(question)
