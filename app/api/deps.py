from typing import Annotated
from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.users import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    try:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise ValueError("Missing bearer token")
        payload = decode_token(credentials.credentials, "access")
        user_id = UUID(payload["sub"])
    except (ValueError, TypeError, KeyError) as exc:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid authentication credentials") from exc
    user = await UserRepository(session).by_id(user_id)
    if not user or not user.is_active:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid authentication credentials")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
