import asyncio

from sqlalchemy import text

from app.core.db import engine
from app.core.redis import redis_client
from app.schemas.system import ReadinessResponse


async def readiness() -> ReadinessResponse:
    async def database_ready() -> bool:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def redis_ready() -> bool:
        try:
            return bool(await redis_client.ping())
        except Exception:
            return False

    database, redis = await asyncio.gather(database_ready(), redis_ready())
    return ReadinessResponse(
        status="ready" if database and redis else "not_ready",
        database=database,
        redis=redis,
    )
