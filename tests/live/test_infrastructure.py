import os
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import status
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import engine
from app.core.exceptions import AppError
from app.core.rate_limit import RedisRateLimiter
from app.core.redis import redis_client
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.repositories.chunks import ChunkRepository
from app.services.health_service import readiness

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_TESTS") != "1",
        reason="Set RUN_LIVE_TESTS=1 with dedicated PostgreSQL and Redis services",
    ),
]


@pytest.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE messages, conversations, ingestion_jobs, document_chunks, "
                "documents, users RESTART IDENTITY CASCADE"
            )
        )
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def test_migrations_vector_extension_and_dependencies() -> None:
    expected_revision = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    async with engine.connect() as connection:
        extension = await connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        fts_index = await connection.scalar(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'document_chunks' "
                "AND indexname = 'ix_document_chunks_content_fts'"
            )
        )
    assert extension
    assert revision == expected_revision
    assert fts_index == "ix_document_chunks_content_fts"
    result = await readiness()
    assert result.status == "ready"
    assert result.database is True
    assert result.redis is True


async def test_pgvector_search_isolated_by_user() -> None:
    first_user = User(email="first@example.com", hashed_password="not-used")
    second_user = User(email="second@example.com", hashed_password="not-used")
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(first_user)
        session.add(second_user)
        await session.flush()
        first_document = Document(
            user_id=first_user.id,
            name="First",
            original_filename="first.txt",
            content_type="text/plain",
            storage_key=f"{uuid4()}.txt",
            file_size=10,
            status="ready",
        )
        second_document = Document(
            user_id=second_user.id,
            name="Second",
            original_filename="second.txt",
            content_type="text/plain",
            storage_key=f"{uuid4()}.txt",
            file_size=10,
            status="ready",
        )
        session.add(first_document)
        session.add(second_document)
        await session.flush()
        vector = [1.0] + [0.0] * 1023
        session.add(
            DocumentChunk(
                document_id=first_document.id,
                user_id=first_user.id,
                content="Visible to the first user",
                embedding=vector,
                chunk_index=0,
            )
        )
        session.add(
            DocumentChunk(
                document_id=second_document.id,
                user_id=second_user.id,
                content="Must never leak secretkeyword to the first user",
                embedding=vector,
                chunk_index=0,
            )
        )
        session.add(
            DocumentChunk(
                document_id=first_document.id,
                user_id=first_user.id,
                content="Owned lexical match for secretkeyword",
                embedding=[0.0, 1.0] + [0.0] * 1022,
                chunk_index=1,
            )
        )
        await session.commit()
        results = await ChunkRepository(session).similarity_search(
            user_id=first_user.id,
            query_text="secretkeyword",
            query_embedding=vector,
            document_ids=None,
            top_k=2,
            min_score=0.9,
        )
    assert {result.chunk.content for result in results} == {
        "Visible to the first user",
        "Owned lexical match for secretkeyword",
    }
    assert all("Must never leak" not in result.chunk.content for result in results)


async def test_real_redis_rate_limit() -> None:
    limiter = RedisRateLimiter()
    action = f"live-{uuid4()}"
    await limiter.check(action=action, identities=["identity"], limit=1, window_seconds=60)
    with pytest.raises(AppError) as captured:
        await limiter.check(action=action, identities=["identity"], limit=1, window_seconds=60)
    assert captured.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert captured.value.headers and "Retry-After" in captured.value.headers
