from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self, status_code: int, detail: str, headers: dict[str, str] | None = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )
