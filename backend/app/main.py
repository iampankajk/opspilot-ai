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
from app.catalog import initialize_catalog
from app.config import Settings, validate_findings_deadline
from app.database import build_engine, check_database, expected_schema_revision
from app.evidence import router as evidence_router
from app.findings import router as findings_router
from app.findings_provider import MockFindingsProvider
from app.investigations import router as investigation_router
from app.visitor_sessions import clear_session_cookie
from app.visitor_sessions import router as visitor_router

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["connected"] = "connected"
    schema_status: Literal["current"] = Field(default="current", alias="schema")


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: dict | None = None,
    retryable: bool | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "retryable": status == 503 if retryable is None else retryable,
                "details": details or {},
            }
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings or Settings.from_env()
        # Recheck explicitly supplied settings too: model_copy(update=...) skips validation.
        try:
            validate_findings_deadline(app.state.settings.ai_findings_deadline_seconds)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from None
        app.state.engine = build_engine(app.state.settings)
        app.state.schema_revision = expected_schema_revision()
        app.state.findings_provider = (
            MockFindingsProvider()
            if app.state.settings.ai_findings_enabled
            and app.state.settings.ai_findings_provider == "mock"
            else None
        )
        app.state.catalog = None
        app.state.catalog_error = None
        try:
            app.state.catalog = initialize_catalog(
                app.state.engine, app.state.settings.current_dataset_version
            )
        except APIError as exc:
            app.state.catalog_error = exc
        except SQLAlchemyError:
            app.state.catalog_error = APIError(
                503, "DATABASE_UNAVAILABLE", "Database is unavailable."
            )
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="OpsPilot AI API", version="0.1.0", lifespan=lifespan)
    app.include_router(visitor_router)
    app.include_router(investigation_router)
    app.include_router(evidence_router)
    app.include_router(findings_router)

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
        response = error_response(
            request, exc.status, exc.code, exc.message, exc.details, exc.retryable
        )
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
        if request.app.state.catalog_error:
            raise request.app.state.catalog_error
        return HealthResponse()

    return app


app = create_app()
