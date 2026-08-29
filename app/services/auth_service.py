from uuid import UUID

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import AppError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse


def token_pair(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_token(subject, "access"),
        refresh_token=create_token(subject, "refresh"),
    )


async def register(session: AsyncSession, data: RegisterRequest) -> User:
    repository = UserRepository(session)
    email = str(data.email).lower()
    if await repository.by_email(email):
        raise AppError(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    try:
        return await repository.save(user)
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from exc


async def login(session: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await UserRepository(session).by_email(email)
    if not user or not verify_password(password, user.hashed_password):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise AppError(status.HTTP_403_FORBIDDEN, "Account is inactive")
    return token_pair(user)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, "refresh")
        user_id = UUID(payload["sub"])
    except (ValueError, TypeError, KeyError) as exc:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    user = await UserRepository(session).by_id(user_id)
    if not user or not user.is_active:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return token_pair(user)
