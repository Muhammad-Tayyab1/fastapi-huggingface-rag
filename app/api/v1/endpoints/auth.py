from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.rate_limit import client_ip, rate_limiter
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, session: SessionDep, request: Request) -> UserRead:
    await rate_limiter.check(
        action="register",
        identities=[client_ip(request), str(data.email)],
        limit=settings.register_rate_limit_per_hour,
        window_seconds=3600,
    )
    return UserRead.model_validate(await auth_service.register(session, data))


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: SessionDep, request: Request) -> TokenResponse:
    await rate_limiter.check(
        action="login",
        identities=[client_ip(request), str(data.email)],
        limit=settings.login_rate_limit_per_15_min,
        window_seconds=900,
    )
    return await auth_service.login(session, str(data.email).lower(), data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, session: SessionDep, request: Request) -> TokenResponse:
    await rate_limiter.check(
        action="refresh",
        identities=[client_ip(request), data.refresh_token],
        limit=settings.login_rate_limit_per_15_min * 3,
        window_seconds=900,
    )
    return await auth_service.refresh(session, data.refresh_token)
