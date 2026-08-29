from httpx import AsyncClient

API = "/api/v1"


async def test_register_login_refresh_and_profile(client: AsyncClient) -> None:
    registration = {
        "email": "person@example.com",
        "password": "very-secure-password",
        "full_name": "Example Person",
    }
    response = await client.post(f"{API}/auth/register", json=registration)
    assert response.status_code == 201
    assert response.json()["email"] == registration["email"]
    assert "hashed_password" not in response.json()

    response = await client.post(
        f"{API}/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert response.status_code == 200
    tokens = response.json()

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = await client.get(f"{API}/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == registration["full_name"]

    response = await client.patch(f"{API}/users/me", headers=headers, json={"full_name": "Updated"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated"

    response = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_duplicate_registration_is_rejected(client: AsyncClient) -> None:
    data = {"email": "duplicate@example.com", "password": "very-secure-password"}
    assert (await client.post(f"{API}/auth/register", json=data)).status_code == 201
    response = await client.post(f"{API}/auth/register", json=data)
    assert response.status_code == 409


async def test_invalid_login_and_protected_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert (await client.get(f"{API}/users/me")).status_code == 401
