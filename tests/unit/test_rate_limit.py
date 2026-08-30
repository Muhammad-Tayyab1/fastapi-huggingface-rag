import pytest

from app.core.exceptions import AppError
from app.core.rate_limit import RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def eval(self, _script, _number_of_keys, key, window):
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], window]


async def test_distributed_rate_limit_returns_retry_after(monkeypatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr("app.core.rate_limit.redis_client", fake)
    limiter = RedisRateLimiter()
    await limiter.check(action="login", identities=["ip", "email"], limit=1, window_seconds=60)
    with pytest.raises(AppError) as captured:
        await limiter.check(action="login", identities=["ip", "email"], limit=1, window_seconds=60)
    assert captured.value.status_code == 429
    assert captured.value.headers == {"Retry-After": "60"}


async def test_rate_limit_keys_do_not_contain_personal_data(monkeypatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr("app.core.rate_limit.redis_client", fake)
    await RedisRateLimiter().check(
        action="register",
        identities=["person@example.com"],
        limit=5,
        window_seconds=60,
    )
    assert all("person@example.com" not in key for key in fake.counts)
