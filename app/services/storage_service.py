from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

import anyio
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


class LocalStorageService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.local_storage_path).resolve()

    async def save(self, upload: UploadFile, user_id: UUID) -> StoredFile:
        original_filename = Path(upload.filename or "document").name
        directory = self.root / str(user_id)
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
            return StoredFile(
                storage_key=str(final_path.relative_to(self.root)),
                content_type=content_type,
                file_size=size,
            )
        except Exception:
            await anyio.Path(temporary).unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    async def delete(self, storage_key: str) -> None:
        path = (self.root / storage_key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        await anyio.Path(path).unlink(missing_ok=True)
