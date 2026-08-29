import io
import zipfile

from httpx import AsyncClient

API = "/api/v1"


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    password = "very-secure-password"
    await client.post(f"{API}/auth/register", json={"email": email, "password": password})
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def minimal_docx() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document><p>Hello</p></document>")
    return output.getvalue()


async def test_document_upload_list_status_and_delete(client: AsyncClient) -> None:
    headers = await auth_headers(client, "documents@example.com")
    response = await client.post(
        f"{API}/documents/",
        headers=headers,
        data={"name": "Project requirements"},
        files={"file": ("requirements.txt", b"The system shall answer questions.\n", "text/plain")},
    )
    assert response.status_code == 202
    payload = response.json()
    document_id = payload["document"]["id"]
    assert payload["document"]["content_type"] == "text/plain"
    assert payload["job"]["status"] == "queued"

    response = await client.get(f"{API}/documents/", headers=headers)
    assert [document["id"] for document in response.json()] == [document_id]

    response = await client.get(f"{API}/documents/{document_id}/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["job"]["progress"] == 0

    response = await client.post(f"{API}/documents/{document_id}/reprocess", headers=headers)
    assert response.status_code == 409

    response = await client.delete(f"{API}/documents/{document_id}", headers=headers)
    assert response.status_code == 204
    assert (await client.get(f"{API}/documents/{document_id}", headers=headers)).status_code == 404


async def test_pdf_docx_and_content_validation(client: AsyncClient) -> None:
    headers = await auth_headers(client, "formats@example.com")
    pdf = await client.post(
        f"{API}/documents/",
        headers=headers,
        files={"file": ("renamed.bin", b"%PDF-1.4\n%%EOF", "application/octet-stream")},
    )
    assert pdf.status_code == 202
    assert pdf.json()["document"]["content_type"] == "application/pdf"

    docx = await client.post(
        f"{API}/documents/",
        headers=headers,
        files={"file": ("document.docx", minimal_docx(), "application/octet-stream")},
    )
    assert docx.status_code == 202
    assert "wordprocessingml" in docx.json()["document"]["content_type"]

    invalid = await client.post(
        f"{API}/documents/",
        headers=headers,
        files={"file": ("malware.exe", b"MZ-not-a-document", "application/octet-stream")},
    )
    assert invalid.status_code == 415


async def test_document_ownership_is_hidden(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner@example.com")
    response = await client.post(
        f"{API}/documents/",
        headers=owner_headers,
        files={"file": ("private.txt", b"private content", "text/plain")},
    )
    document_id = response.json()["document"]["id"]

    other_headers = await auth_headers(client, "other@example.com")
    response = await client.get(f"{API}/documents/{document_id}", headers=other_headers)
    assert response.status_code == 404
