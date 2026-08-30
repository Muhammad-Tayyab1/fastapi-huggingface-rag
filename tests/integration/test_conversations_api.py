from uuid import UUID, uuid4

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


async def test_conversation_crud_and_ownership(client: AsyncClient) -> None:
    owner = await auth_headers(client, "conversation-owner@example.com")
    response = await client.post(
        f"{API}/conversations/", headers=owner, json={"title": "Policy questions"}
    )
    assert response.status_code == 201
    conversation_id = response.json()["id"]

    response = await client.get(f"{API}/conversations/", headers=owner)
    assert [item["id"] for item in response.json()] == [conversation_id]

    response = await client.get(f"{API}/conversations/{conversation_id}", headers=owner)
    assert response.status_code == 200
    assert response.json()["messages"] == []

    other = await auth_headers(client, "conversation-other@example.com")
    assert (
        await client.get(f"{API}/conversations/{conversation_id}", headers=other)
    ).status_code == 404

    assert (
        await client.delete(f"{API}/conversations/{conversation_id}", headers=owner)
    ).status_code == 204
    assert (
        await client.get(f"{API}/conversations/{conversation_id}", headers=owner)
    ).status_code == 404


async def test_messages_and_citations_are_persisted(
    client: AsyncClient, session: AsyncSession
) -> None:
    headers = await auth_headers(client, "message-owner@example.com")
    created = await client.post(f"{API}/conversations/", headers=headers, json={"title": "Sources"})
    conversation = await session.get(Conversation, UUID(created.json()["id"]))
    source = {
        "chunk_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_name": "policy.pdf",
        "page_number": 2,
        "score": 0.91,
        "excerpt": "Relevant policy text",
    }
    await ConversationRepository(session).save_exchange(
        conversation, "What is the policy?", "The answer", [source]
    )
    response = await client.get(f"{API}/conversations/{conversation.id}/messages", headers=headers)
    assert response.status_code == 200
    messages = response.json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["sources"][0]["page_number"] == 2
