from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

import anyio
import boto3
from fastapi import UploadFile, status

from app.core.config import settings
from app.core.exceptions import AppError

CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    content_type: str
    file_size: int


def _detect_type(path: Path, original_filename: str) -> tuple[str, str] | None:
    with path.open("rb") as file:
        header = file.read(8)
    if header.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" in names and "word/document.xml" in names:
                return (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".docx",
                )
    except BadZipFile:
        pass
    if Path(original_filename).suffix.lower() == ".txt":
        try:
            path.read_text(encoding="utf-8")
            return "text/plain", ".txt"
        except UnicodeDecodeError:
            pass
    return None


async def _stage_upload(upload: UploadFile, directory: Path) -> tuple[Path, str, int]:
    original_filename = Path(upload.filename or "document").name
    await anyio.Path(directory).mkdir(parents=True, exist_ok=True)
    temporary = directory / f"{uuid4()}.upload"
    size = 0
    maximum = settings.max_upload_mb * 1024 * 1024
    try:
        async with await anyio.open_file(temporary, "wb") as target:
            while chunk := await upload.read(CHUNK_BYTES):
                size += len(chunk)
                if size > maximum:
                    raise AppError(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"File exceeds the {settings.max_upload_mb} MB limit",
                    )
                await target.write(chunk)
        if size == 0:
            raise AppError(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
        detected = await anyio.to_thread.run_sync(_detect_type, temporary, original_filename)
        if detected is None:
            raise AppError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Only valid PDF, DOCX, and UTF-8 TXT files are supported",
            )
        content_type, suffix = detected
        final_path = temporary.with_suffix(suffix)
        await anyio.Path(temporary).rename(final_path)
        return final_path, content_type, size
    except Exception:
        await anyio.Path(temporary).unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def _validate_key(storage_key: str) -> Path:
    key = Path(storage_key)
    if key.is_absolute() or ".." in key.parts or not storage_key:
        raise ValueError("Invalid storage key")
    return key


class StorageService(ABC):
    @abstractmethod
    async def save(self, upload: UploadFile, user_id: UUID) -> StoredFile: ...

    @abstractmethod
    async def delete(self, storage_key: str) -> None: ...

    @abstractmethod
    def materialize(self, storage_key: str) -> AsyncIterator[Path]: ...


class LocalStorageService(StorageService):
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.local_storage_path).resolve()

    async def save(self, upload: UploadFile, user_id: UUID) -> StoredFile:
        final_path, content_type, size = await _stage_upload(upload, self.root / str(user_id))
        return StoredFile(
            storage_key=str(final_path.relative_to(self.root)),
            content_type=content_type,
            file_size=size,
        )

    async def delete(self, storage_key: str) -> None:
        path = (self.root / _validate_key(storage_key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        await anyio.Path(path).unlink(missing_ok=True)

    @asynccontextmanager
    async def materialize(self, storage_key: str) -> AsyncIterator[Path]:
        path = (self.root / _validate_key(storage_key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        if not await anyio.Path(path).is_file():
            raise FileNotFoundError(storage_key)
        yield path


class S3StorageService(StorageService):
    def __init__(
        self, *, bucket: str | None = None, prefix: str | None = None, client: Any = None
    ) -> None:
        self.bucket = bucket or settings.s3_bucket
        if not self.bucket:
            raise ValueError("S3 bucket is required")
        self.prefix = (settings.s3_prefix if prefix is None else prefix).strip("/")
        self.client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        return boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id.get_secret_value() or None,
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value() or None,
        )

    async def save(self, upload: UploadFile, user_id: UUID) -> StoredFile:
        with TemporaryDirectory(prefix="rag-upload-") as directory:
            path, content_type, size = await _stage_upload(upload, Path(directory))
            parts = [
                part for part in (self.prefix, str(user_id), f"{uuid4()}{path.suffix}") if part
            ]
            storage_key = "/".join(parts)
            await anyio.to_thread.run_sync(
                lambda: self.client.upload_file(
                    str(path), self.bucket, storage_key, ExtraArgs={"ContentType": content_type}
                )
            )
        return StoredFile(storage_key, content_type, size)

    async def delete(self, storage_key: str) -> None:
        key = _validate_key(storage_key).as_posix()
        await anyio.to_thread.run_sync(
            lambda: self.client.delete_object(Bucket=self.bucket, Key=key)
        )

    @asynccontextmanager
    async def materialize(self, storage_key: str) -> AsyncIterator[Path]:
        key = _validate_key(storage_key).as_posix()
        with TemporaryDirectory(prefix="rag-download-") as directory:
            path = Path(directory) / Path(key).name
            await anyio.to_thread.run_sync(
                lambda: self.client.download_file(self.bucket, key, str(path))
            )
            yield path


def get_storage_service() -> StorageService:
    if settings.storage_backend == "s3":
        return S3StorageService()
    return LocalStorageService()
