from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(sa_column=Column(String(320), unique=True, index=True, nullable=False))
    hashed_password: str
    full_name: str | None = Field(default=None, max_length=200)
    role: str = Field(default="user", max_length=20)
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
        )
    )
    name: str = Field(max_length=100)
    key_prefix: str = Field(sa_column=Column(String(32), unique=True, index=True, nullable=False))
    key_hash: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    last_used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
