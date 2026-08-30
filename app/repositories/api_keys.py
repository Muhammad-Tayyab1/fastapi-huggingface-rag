from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import api_key_lookup_prefix, api_key_matches
from app.models.base import utcnow
from app.models.user import ApiKey


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, user_id: UUID) -> list[ApiKey]:
        result = await self.session.exec(
            select(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.all())

    async def create(self, api_key: ApiKey) -> ApiKey:
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key

    async def owned(self, key_id: UUID, user_id: UUID) -> ApiKey | None:
        result = await self.session.exec(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
        return result.first()

    async def authenticate(self, raw_key: str) -> ApiKey | None:
        prefix = api_key_lookup_prefix(raw_key)
        if not prefix:
            return None
        now = utcnow()
        result = await self.session.exec(
            select(ApiKey).where(
                ApiKey.key_prefix == prefix,
                ApiKey.revoked_at.is_(None),
                or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
            )
        )
        api_key = result.first()
        if not api_key or not api_key_matches(raw_key, api_key.key_hash):
            return None
        last_used = api_key.last_used_at
        if last_used and last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=UTC)
        if not last_used or last_used < now - timedelta(minutes=5):
            api_key.last_used_at = now
            self.session.add(api_key)
            await self.session.commit()
        return api_key

    async def revoke(self, api_key: ApiKey) -> None:
        api_key.revoked_at = utcnow()
        self.session.add(api_key)
        await self.session.commit()
