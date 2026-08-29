from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentStatus = Literal["uploaded", "processing", "extracted", "ready", "failed"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    original_filename: str
    content_type: str
    file_size: int
    status: DocumentStatus
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: JobStatus
    progress: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
    job: IngestionJobRead | None
