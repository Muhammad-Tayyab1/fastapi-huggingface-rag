from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.services.storage_service import LocalStorageService, S3StorageService


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str]]] = {}

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict[str, str]) -> None:
        self.objects[(bucket, key)] = (Path(filename).read_bytes(), ExtraArgs)

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)][0])

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


@pytest.mark.asyncio
async def test_local_storage_materializes_saved_file(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)
    stored = await service.save(UploadFile(BytesIO(b"hello"), filename="note.txt"), uuid4())

    async with service.materialize(stored.storage_key) as path:
        assert path.read_text() == "hello"

    await service.delete(stored.storage_key)
    with pytest.raises(FileNotFoundError):
        async with service.materialize(stored.storage_key):
            pass


@pytest.mark.asyncio
async def test_s3_storage_upload_download_and_delete() -> None:
    client = FakeS3Client()
    user_id = uuid4()
    service = S3StorageService(bucket="rag", prefix="documents", client=client)

    stored = await service.save(UploadFile(BytesIO(b"hello"), filename="note.txt"), user_id)

    assert stored.storage_key.startswith(f"documents/{user_id}/")
    assert stored.storage_key.endswith(".txt")
    assert stored.content_type == "text/plain"
    assert stored.file_size == 5
    assert client.objects[("rag", stored.storage_key)][1] == {"ContentType": "text/plain"}

    async with service.materialize(stored.storage_key) as path:
        assert path.read_bytes() == b"hello"
        materialized = path
    assert not materialized.exists()

    await service.delete(stored.storage_key)
    assert client.objects == {}


@pytest.mark.asyncio
async def test_storage_rejects_path_traversal(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    with pytest.raises(ValueError, match="Invalid storage key"):
        await service.delete("../outside.txt")
