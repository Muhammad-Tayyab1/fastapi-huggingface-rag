from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.document import Document, IngestionJob


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def owned(self, document_id: UUID, user_id: UUID) -> Document | None:
        result = await self.session.exec(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        return result.first()

    async def list_owned(self, user_id: UUID, offset: int = 0, limit: int = 20) -> list[Document]:
        result = await self.session.exec(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def latest_job(self, document_id: UUID, user_id: UUID) -> IngestionJob | None:
        result = await self.session.exec(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id, IngestionJob.user_id == user_id)
            .order_by(IngestionJob.created_at.desc())
        )
        return result.first()

    async def create_with_job(
        self, document: Document, job: IngestionJob
    ) -> tuple[Document, IngestionJob]:
        self.session.add(document)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(document)
        await self.session.refresh(job)
        return document, job

    async def create_job(self, job: IngestionJob) -> IngestionJob:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
        await self.session.commit()
