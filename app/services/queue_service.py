from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_ingestion(document_id: UUID, job_id: UUID) -> None:
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job(
            "process_document",
            str(document_id),
            str(job_id),
            _job_id=f"ingestion:{job_id}",
        )
    finally:
        await pool.aclose()
