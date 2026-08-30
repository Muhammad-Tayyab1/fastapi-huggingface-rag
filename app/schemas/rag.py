from uuid import UUID

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=50)
    top_k: int | None = Field(default=None, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0, le=1)


class RAGSource(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int | None
    score: float
    excerpt: str


class RAGSearchResponse(BaseModel):
    question: str
    sources: list[RAGSource]


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[RAGSource]
    grounded: bool
