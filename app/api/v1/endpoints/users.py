from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models.base import utcnow
from app.repositories.users import UserRepository
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep) -> UserRead:
    user.full_name = data.full_name
    user.updated_at = utcnow()
    return UserRead.model_validate(await UserRepository(session).save(user))
