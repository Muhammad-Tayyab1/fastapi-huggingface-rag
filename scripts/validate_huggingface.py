import asyncio

from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService


async def main() -> None:
    embedding = await EmbeddingService().embed_query("Hugging Face connectivity check")
    if not embedding:
        raise RuntimeError("Embedding provider returned no vector")
    answer = await LLMService().answer(
        "What phrase appears in the context?",
        "[Source 1: smoke-test.txt]\nThe deployment smoke test is working.",
    )
    if not answer:
        raise RuntimeError("Chat provider returned no answer")
    print(f"Embedding dimension: {len(embedding)}")
    print("Chat completion: OK")


if __name__ == "__main__":
    asyncio.run(main())
