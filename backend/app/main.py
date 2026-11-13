import logging
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api_errors import APIError
from app.config import Settings
from app.database import build_engine, check_database, expected_schema_revision
from app.visitor_sessions import clear_session_cookie
from app.visitor_sessions import router as visitor_router

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["connected"] = "connected"
    schema_status: Literal["current"] = Field(default="current", alias="schema")


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "retryable": status == 503,
                "details": {},
            }
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings or Settings.from_env()
        app.state.engine = build_engine(app.state.settings)
        app.state.schema_revision = expected_schema_revision()
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="OpsPilot AI API", version="0.1.0", lifespan=lifespan)
    app.include_router(visitor_router)

    @app.middleware("http")
    async def api_boundary(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = None
        if request.method == "POST":
            if (
                request.headers.get("origin") != request.app.state.settings.public_origin
                or request.headers.get("x-opspilot-request") != "1"
            ):
                response = error_response(
                    request,
                    403,
                    "REQUEST_ORIGIN_FORBIDDEN",
                    "A same-origin application request is required.",
                )
            elif (
                request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                response = error_response(
                    request, 415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json."
                )
            # Bound the body even if Content-Length is absent or dishonest.
            else:
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 4096:
                        response = error_response(
                            request, 413, "PAYLOAD_TOO_LARGE", "Request body exceeds 4 KiB."
                        )
                        break
                    body.extend(chunk)
                if response is None:
                    request._body = bytes(body)
        if response is None:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Never serialize exception/SQL/validation input into public responses.
                logger.error(
                    "Request failed: request_id=%s exception_type=%s",
                    request.state.request_id,
                    type(exc).__name__,
                )
                response = error_response(
                    request, 500, "INTERNAL_ERROR", "An internal error occurred."
                )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return error_response(request, exc.status_code, code, "Request could not be served.")

    @app.exception_handler(APIError)
    async def application_error(request: Request, exc: APIError):
        response = error_response(request, exc.status, exc.code, exc.message)
        if exc.clear_cookie:
            clear_session_cookie(response)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Database request failed: request_id=%s exception_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "Database is unavailable.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health(request: Request):
        code = check_database(request.app.state.engine, request.app.state.schema_revision)
        if code:
            message = (
                "Database schema is not current; run the explicit Alembic upgrade."
                if code == "SCHEMA_NOT_READY"
                else "Database is unavailable."
            )
            return error_response(request, 503, code, message)
        return HealthResponse()

    return app


app = create_app()
