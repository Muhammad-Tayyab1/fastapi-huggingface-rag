from pathlib import Path
from uuid import UUID

from fastapi import UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import AppError
from app.models.document import Document, IngestionJob
from app.repositories.documents import DocumentRepository
from app.schemas.document import DocumentStatusResponse, DocumentUploadResponse
from app.services.storage_service import LocalStorageService


async def owned_document(session: AsyncSession, document_id: UUID, user_id: UUID) -> Document:
    document = await DocumentRepository(session).owned(document_id, user_id)
    if not document:
        raise AppError(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


async def upload_document(
    session: AsyncSession,
    user_id: UUID,
    upload: UploadFile,
    name: str | None,
) -> DocumentUploadResponse:
    storage = LocalStorageService()
    stored = await storage.save(upload, user_id)
    original_filename = Path(upload.filename or "document").name
    document = Document(
        user_id=user_id,
        name=(name or Path(original_filename).stem)[:255],
        original_filename=original_filename[:255],
        content_type=stored.content_type,
        storage_key=stored.storage_key,
        file_size=stored.file_size,
    )
    job = IngestionJob(document_id=document.id, user_id=user_id)
    try:
        document, job = await DocumentRepository(session).create_with_job(document, job)
    except Exception:
        await session.rollback()
        await storage.delete(stored.storage_key)
        raise
    return DocumentUploadResponse(document=document, job=job)


async def document_status(
    session: AsyncSession, document_id: UUID, user_id: UUID
) -> DocumentStatusResponse:
    document = await owned_document(session, document_id, user_id)
    job = await DocumentRepository(session).latest_job(document.id, user_id)
    return DocumentStatusResponse(document_id=document.id, status=document.status, job=job)


async def reprocess(session: AsyncSession, document_id: UUID, user_id: UUID) -> IngestionJob:
    document = await owned_document(session, document_id, user_id)
    latest = await DocumentRepository(session).latest_job(document.id, user_id)
    if latest and latest.status in {"queued", "processing"}:
        raise AppError(status.HTTP_409_CONFLICT, "Document processing is already active")
    job = IngestionJob(document_id=document.id, user_id=user_id)
    document.status = "uploaded"
    document.error_message = None
    session.add(document)
    return await DocumentRepository(session).create_job(job)


async def delete_document(session: AsyncSession, document_id: UUID, user_id: UUID) -> None:
    document = await owned_document(session, document_id, user_id)
    await LocalStorageService().delete(document.storage_key)
    await DocumentRepository(session).delete(document)
