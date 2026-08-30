import hashlib

from fastapi import Request, status
from redis.exceptions import RedisError

from app.core.exceptions import AppError
from app.core.redis import redis_client

RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _safe_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class RedisRateLimiter:
    async def check(
        self,
        *,
        action: str,
        identities: list[str],
        limit: int,
        window_seconds: int,
    ) -> None:
        try:
            results = []
            for identity in identities:
                key = f"rate-limit:{action}:{_safe_key(identity.lower())}"
                result = await redis_client.eval(RATE_LIMIT_SCRIPT, 1, key, window_seconds)
                results.append((int(result[0]), max(1, int(result[1]))))
        except RedisError as exc:
            raise AppError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Request protection service is temporarily unavailable",
            ) from exc
        exceeded = [item for item in results if item[0] > limit]
        if exceeded:
            retry_after = max(item[1] for item in exceeded)
            raise AppError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests",
                headers={"Retry-After": str(retry_after)},
            )


rate_limiter = RedisRateLimiter()
