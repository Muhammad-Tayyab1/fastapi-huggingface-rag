from httpx import ASGITransport, AsyncClient

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
