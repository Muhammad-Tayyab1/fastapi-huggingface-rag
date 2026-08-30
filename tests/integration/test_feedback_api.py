from uuid import UUID

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.conversation import Conversation
from app.repositories.conversations import ConversationRepository

API = "/api/v1"


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    password = "very-secure-password"
    await client.post(f"{API}/auth/register", json={"email": email, "password": password})
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def assistant_message(
    client: AsyncClient, session: AsyncSession, headers: dict[str, str]
) -> str:
    created = await client.post(
        f"{API}/conversations/", headers=headers, json={"title": "Feedback test"}
    )
    conversation = await session.get(Conversation, UUID(created.json()["id"]))
    _, answer = await ConversationRepository(session).save_exchange(
        conversation, "Question", "Answer", []
    )
    return str(answer.id)


async def test_feedback_crud_and_summary(client: AsyncClient, session: AsyncSession) -> None:
    headers = await auth_headers(client, "feedback-owner@example.com")
    message_id = await assistant_message(client, session, headers)

    response = await client.put(
        f"{API}/feedback/messages/{message_id}",
        headers=headers,
        json={"rating": "up", "comment": "Grounded and useful"},
    )
    assert response.status_code == 200
    assert response.json()["rating"] == "up"

    response = await client.put(
        f"{API}/feedback/messages/{message_id}",
        headers=headers,
        json={"rating": "down", "comment": "Citation was incomplete"},
    )
    assert response.status_code == 200
    assert response.json()["rating"] == "down"

    response = await client.get(f"{API}/feedback/messages/{message_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["comment"] == "Citation was incomplete"

    response = await client.get(f"{API}/feedback/summary", headers=headers)
    assert response.json() == {
        "total": 1,
        "positive": 0,
        "negative": 1,
        "positive_rate": 0.0,
    }

    assert (
        await client.delete(f"{API}/feedback/messages/{message_id}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"{API}/feedback/messages/{message_id}", headers=headers)
    ).status_code == 404


async def test_feedback_enforces_message_ownership(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await auth_headers(client, "feedback-private@example.com")
    message_id = await assistant_message(client, session, owner)
    other = await auth_headers(client, "feedback-other@example.com")

    response = await client.put(
        f"{API}/feedback/messages/{message_id}",
        headers=other,
        json={"rating": "up"},
    )
    assert response.status_code == 404


async def test_feedback_only_accepts_assistant_messages(
    client: AsyncClient, session: AsyncSession
) -> None:
    headers = await auth_headers(client, "feedback-role@example.com")
    created = await client.post(
        f"{API}/conversations/", headers=headers, json={"title": "Role test"}
    )
    conversation = await session.get(Conversation, UUID(created.json()["id"]))
    question, _ = await ConversationRepository(session).save_exchange(
        conversation, "Question", "Answer", []
    )

    response = await client.put(
        f"{API}/feedback/messages/{question.id}",
        headers=headers,
        json={"rating": "up"},
    )
    assert response.status_code == 404


async def test_feedback_validates_payload(client: AsyncClient, session: AsyncSession) -> None:
    headers = await auth_headers(client, "feedback-validation@example.com")
    message_id = await assistant_message(client, session, headers)

    response = await client.put(
        f"{API}/feedback/messages/{message_id}",
        headers=headers,
        json={"rating": "maybe"},
    )
    assert response.status_code == 422
