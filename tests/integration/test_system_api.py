from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app


async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


async def test_valid_request_id_is_propagated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/health", headers={"X-Request-ID": "frontend-request-123"}
        )
    assert response.headers["X-Request-ID"] == "frontend-request-123"


async def test_invalid_request_id_is_replaced() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/health", headers={"X-Request-ID": "invalid request id"}
        )
    assert response.headers["X-Request-ID"] != "invalid request id"


async def test_metrics_require_token_and_expose_low_cardinality_data(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metrics_enabled", True)
    monkeypatch.setattr(settings, "metrics_bearer_token", SecretStr("scrape"))
    queue_depth = AsyncMock(return_value=3)
    monkeypatch.setattr("app.main.redis_client.zcard", queue_depth)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/metrics")).status_code == 401
        response = await client.get("/metrics", headers={"Authorization": "Bearer scrape"})

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "rag_api_http_requests_total" in response.text
    assert "rag_api_arq_queue_depth 3.0" in response.text
    assert "frontend-request-123" not in response.text
    queue_depth.assert_awaited_with(settings.arq_queue_name)
