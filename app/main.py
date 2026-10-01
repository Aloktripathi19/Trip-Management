import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import trips
from app.database import SessionLocal
from app.exceptions import AppError

logger = logging.getLogger("trip_api")


def _error(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trip Management API",
        version="1.0.0",
        description="Create, query and progress trips through a validated status lifecycle.",
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p not in ("body",)),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return _error(422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "An unexpected error occurred")

    @app.get("/health", tags=["health"])
    def health():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(trips.router)
    return app


app = create_app()
