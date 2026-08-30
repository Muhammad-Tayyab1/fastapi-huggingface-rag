import asyncio
import math
from collections.abc import Awaitable, Callable
from typing import Any

from huggingface_hub import AsyncInferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.core.config import settings
from app.repositories.chunks import RetrievedChunk

Sleep = Callable[[float], Awaitable[None]]


class RerankingService:
    def __init__(
        self,
        client: Any | None = None,
        *,
        max_retries: int | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        token = settings.hf_token.get_secret_value()
        if client is None and not token:
            raise RuntimeError("HF_TOKEN is required for reranking")
        self.client = client or AsyncInferenceClient(
            provider=settings.hf_provider,
            api_key=token,
            timeout=settings.hf_timeout_seconds,
        )
        self.max_retries = max_retries or settings.hf_max_retries
        self.sleep = sleep

    async def _scores(self, question: str, passages: list[str]) -> list[float]:
        for attempt in range(1, self.max_retries + 1):
            try:
                values = await self.client.sentence_similarity(
                    question,
                    other_sentences=passages,
                    model=settings.hf_reranker_model,
                )
                return [float(value) for value in values]
            except (HfHubHTTPError, InferenceTimeoutError) as exc:
                if attempt == self.max_retries:
                    raise RuntimeError("Hugging Face reranking request failed") from exc
                await self.sleep(2 ** (attempt - 1))
        raise RuntimeError("Hugging Face reranking request failed")

    async def rerank(
        self, question: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        scores = await self._scores(question, [candidate.chunk.content for candidate in candidates])
        if len(scores) != len(candidates):
            raise ValueError(
                f"Reranking count mismatch: expected {len(candidates)}, received {len(scores)}"
            )
        if not all(math.isfinite(score) for score in scores):
            raise ValueError("Reranking response contains a non-finite score")
        ranked = sorted(
            zip(candidates, scores, strict=True), key=lambda item: item[1], reverse=True
        )
        return [
            RetrievedChunk(
                chunk=candidate.chunk,
                document_name=candidate.document_name,
                score=round(max(0.0, min(1.0, (score + 1) / 2)), 6),
            )
            for candidate, score in ranked[:top_k]
        ]
