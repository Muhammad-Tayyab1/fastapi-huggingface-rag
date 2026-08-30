from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.api_keys import ApiKeyRepository
from app.repositories.users import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _jwt_user(
    credentials: HTTPAuthorizationCredentials | None, session: AsyncSession
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


async def get_current_jwt_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    return await _jwt_user(credentials, session)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    raw_api_key: Annotated[str | None, Depends(api_key_scheme)],
    request: Request,
    session: SessionDep,
) -> User:
    if raw_api_key:
        api_key = await ApiKeyRepository(session).authenticate(raw_api_key)
        user = await UserRepository(session).by_id(api_key.user_id) if api_key else None
        if not user or not user.is_active:
            raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid authentication credentials")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and "write" not in api_key.scopes:
            raise AppError(status.HTTP_403_FORBIDDEN, "API key does not have write scope")
        return user
    return await _jwt_user(credentials, session)


CurrentUser = Annotated[User, Depends(get_current_user)]
JWTCurrentUser = Annotated[User, Depends(get_current_jwt_user)]
