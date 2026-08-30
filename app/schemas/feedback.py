from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackUpsert(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: UUID
    rating: Literal["up", "down"]
    comment: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackSummary(BaseModel):
    total: int
    positive: int
    negative: int
    positive_rate: float | None
