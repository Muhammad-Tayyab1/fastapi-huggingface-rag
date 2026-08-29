from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        result = await self.session.exec(select(User).where(User.email == email.lower()))
        return result.first()

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def save(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
