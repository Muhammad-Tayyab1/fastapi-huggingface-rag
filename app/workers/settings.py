from arq.connections import RedisSettings
from arq.worker import func

from app.core.config import settings
from app.workers.ingestion import process_document


class WorkerSettings:
    functions = [func(process_document, max_tries=3, timeout=300)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    health_check_interval = 30
