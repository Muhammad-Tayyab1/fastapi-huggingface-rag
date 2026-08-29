import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import close_db
from app.core.exceptions import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.monitoring import init_monitoring
from app.core.redis import close_redis
from app.core.request_context import request_id_context

logger = logging.getLogger("app.access")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


async def request_context_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration = round((time.perf_counter() - started) * 1000, 3)
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration,
            },
        )
        request_id_context.reset(token)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled application error",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id_context.get(),
        },
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    yield
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    configure_logging()
    init_monitoring()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    application.middleware("http")(request_context_middleware)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(Exception, unhandled_error_handler)
    return application


app = create_app()
