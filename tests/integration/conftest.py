from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.document import Document, IngestionJob
from app.models.user import User


@pytest.fixture
async def session(tmp_path) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(Document.__table__.create)
        await connection.run_sync(IngestionJob.__table__.create)
    previous_storage_path = settings.local_storage_path
    settings.local_storage_path = tmp_path / "storage"
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    settings.local_storage_path = previous_storage_path
    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
