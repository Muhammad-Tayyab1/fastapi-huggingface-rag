from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import JWTCurrentUser, SessionDep
from app.core.exceptions import AppError
from app.core.security import create_api_key
from app.models.user import ApiKey
from app.repositories.api_keys import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("/", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    data: ApiKeyCreate, user: JWTCurrentUser, session: SessionDep
) -> ApiKeyCreated:
    raw_key, prefix, key_hash = create_api_key()
    api_key = await ApiKeyRepository(session).create(
        ApiKey(
            user_id=user.id,
            name=data.name,
            key_prefix=prefix,
            key_hash=key_hash,
            expires_at=data.expires_at,
        )
    )
    return ApiKeyCreated(**ApiKeyRead.model_validate(api_key).model_dump(), key=raw_key)


@router.get("/", response_model=list[ApiKeyRead])
async def list_keys(user: JWTCurrentUser, session: SessionDep) -> list[ApiKeyRead]:
    keys = await ApiKeyRepository(session).list_active(user.id)
    return [ApiKeyRead.model_validate(key) for key in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(key_id: UUID, user: JWTCurrentUser, session: SessionDep) -> Response:
    repository = ApiKeyRepository(session)
    api_key = await repository.owned(key_id, user.id)
    if not api_key or api_key.revoked_at:
        raise AppError(status.HTTP_404_NOT_FOUND, "API key not found")
    await repository.revoke(api_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
