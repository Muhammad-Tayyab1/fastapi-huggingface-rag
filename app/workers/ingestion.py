from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import engine
from app.models.document import Document, DocumentChunk, IngestionJob
from app.repositories.documents import DocumentRepository
from app.services.chunking_service import chunk_pages
from app.services.embedding_service import embed_texts
from app.services.extraction_service import extract
from app.services.storage_service import get_storage_service


async def process_document(_: dict[str, Any], document_id: str, job_id: str) -> dict[str, int]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        document = await session.get(Document, UUID(document_id))
        job = await session.get(IngestionJob, UUID(job_id))
        if not document or not job or job.document_id != document.id:
            raise ValueError("Document ingestion job not found")
        try:
            document.status = "processing"
            document.error_message = None
            job.status = "processing"
            job.progress = 5
            job.started_at = datetime.now(UTC)
            session.add(document)
            session.add(job)
            await session.commit()

            async with get_storage_service().materialize(document.storage_key) as path:
                pages = await extract(path, document.content_type)
            if not pages:
                raise ValueError("No extractable text found; scanned PDFs require OCR")
            job.progress = 40
            session.add(job)
            await session.commit()

            chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
            if not chunks:
                raise ValueError("Document produced no text chunks")
            records = [
                DocumentChunk(
                    document_id=document.id,
                    user_id=document.user_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    token_count=chunk.token_count,
                    chunk_metadata={"source": document.original_filename},
                )
                for chunk in chunks
            ]
            await DocumentRepository(session).replace_chunks(document.id, records)
            document.page_count = max(
                (page.page_number or 1 for page in pages),
                default=1,
            )
            document.status = "extracted"
            job.progress = 60
            session.add(document)
            session.add(job)
            await session.commit()

            embeddings = await embed_texts([record.content for record in records])
            for record, embedding in zip(records, embeddings, strict=True):
                record.embedding = embedding
                session.add(record)
            document.status = "ready"
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.now(UTC)
            session.add(document)
            session.add(job)
            await session.commit()
            return {"pages": len(pages), "chunks": len(chunks), "embeddings": len(embeddings)}
        except Exception as exc:
            await session.rollback()
            document.status = "failed"
            document.error_message = str(exc)[:2000]
            job.status = "failed"
            job.error_message = document.error_message
            job.completed_at = datetime.now(UTC)
            session.add(document)
            session.add(job)
            await session.commit()
            raise
