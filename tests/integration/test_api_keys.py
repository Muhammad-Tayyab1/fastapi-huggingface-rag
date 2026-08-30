from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import ApiKey

API = "/api/v1"


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    password = "very-secure-password"
    await client.post(f"{API}/auth/register", json={"email": email, "password": password})
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_api_key_lifecycle_and_authentication(client: AsyncClient) -> None:
    bearer = await auth_headers(client, "api-key-owner@example.com")
    created = await client.post(
        f"{API}/api-keys/", headers=bearer, json={"name": "evaluation runner"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith(f"rag_{body['key_prefix']}.")

    listed = await client.get(f"{API}/api-keys/", headers=bearer)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "evaluation runner"
    assert "key" not in listed.json()[0]

    api_headers = {"X-API-Key": body["key"]}
    profile = await client.get(f"{API}/users/me", headers=api_headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "api-key-owner@example.com"
    assert (await client.get(f"{API}/users/me", headers=api_headers)).status_code == 200

    assert (await client.get(f"{API}/api-keys/", headers=api_headers)).status_code == 401
    assert (await client.delete(f"{API}/api-keys/{body['id']}", headers=bearer)).status_code == 204
    assert (await client.get(f"{API}/users/me", headers=api_headers)).status_code == 401


async def test_api_key_ownership_and_expiration_validation(client: AsyncClient) -> None:
    owner = await auth_headers(client, "api-key-private@example.com")
    created = await client.post(f"{API}/api-keys/", headers=owner, json={"name": "private"})
    other = await auth_headers(client, "api-key-other@example.com")

    assert (
        await client.delete(f"{API}/api-keys/{created.json()['id']}", headers=other)
    ).status_code == 404
    expired = await client.post(
        f"{API}/api-keys/",
        headers=owner,
        json={"name": "expired", "expires_at": "2020-01-01T00:00:00Z"},
    )
    assert expired.status_code == 422


async def test_expired_api_key_cannot_authenticate(
    client: AsyncClient, session: AsyncSession
) -> None:
    bearer = await auth_headers(client, "api-key-expired@example.com")
    created = await client.post(
        f"{API}/api-keys/",
        headers=bearer,
        json={
            "name": "short lived",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    api_key = await session.get(ApiKey, UUID(created.json()["id"]))
    api_key.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(api_key)
    await session.commit()

    response = await client.get(f"{API}/users/me", headers={"X-API-Key": created.json()["key"]})
    assert response.status_code == 401
