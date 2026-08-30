from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def expiration_must_be_future(self) -> "ApiKeyCreate":
        if self.expires_at:
            expiration = self.expires_at
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=UTC)
                self.expires_at = expiration
            if expiration <= datetime.now(UTC):
                raise ValueError("expires_at must be in the future")
        return self


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    key: str
