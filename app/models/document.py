from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.core.config import settings
from app.models.base import utcnow


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    name: str = Field(max_length=255)
    original_filename: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    storage_key: str = Field(sa_column=Column(String(500), unique=True, nullable=False))
    file_size: int = Field(ge=0)
    status: str = Field(default="uploaded", max_length=30, index=True)
    page_count: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    user_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    embedding: Any | None = Field(
        default=None, sa_column=Column(Vector(settings.embedding_dimension), nullable=True)
    )
    chunk_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    token_count: int | None = Field(default=None, ge=0)
    chunk_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class IngestionJob(SQLModel, table=True):
    __tablename__ = "ingestion_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    user_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    status: str = Field(default="queued", max_length=30, index=True)
    progress: int = Field(default=0, ge=0, le=100)
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
