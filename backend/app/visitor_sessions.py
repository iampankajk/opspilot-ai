import hashlib
import re
import secrets
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.models import VisitorContext

COOKIE_NAME = "__Host-opspilot_visitor"
DEV_HTTP_COOKIE_NAME = "opspilot_visitor"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}", flags=re.ASCII)
Clock = Callable[[], datetime]
router = APIRouter(prefix="/api/v1")


@dataclass(frozen=True)
class CookiePolicy:
    name: str
    secure: bool
    httponly: bool = True
    samesite: Literal["lax"] = "lax"
    path: str = "/"


HTTPS_COOKIE_POLICY = CookiePolicy(name=COOKIE_NAME, secure=True)
DEV_HTTP_COOKIE_POLICY = CookiePolicy(name=DEV_HTTP_COOKIE_NAME, secure=False)


def get_cookie_policy(request: Request) -> CookiePolicy:
    settings = request.app.state.settings
    if settings.allow_insecure_local_http and urlsplit(settings.public_origin).scheme == "http":
        return DEV_HTTP_COOKIE_POLICY
    return HTTPS_COOKIE_POLICY


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(get_cookie_policy(request).name)


def get_clock() -> Clock:
    # A dependency permits deterministic expiry tests without request-controlled time.
    return lambda: datetime.now(UTC)


class VisitorSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisitorSession(BaseModel):
    model_config = ConfigDict(frozen=True)
    visitor_context_id: UUID
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


def session_failure(code: str) -> APIError:
    messages = {
        "SESSION_REQUIRED": "A visitor session is required. Start a fresh demo to continue.",
        "SESSION_INVALID": "The visitor session is invalid. Start a fresh demo to continue.",
        "SESSION_EXPIRED": "The visitor session expired. Start a fresh demo to continue.",
    }
    return APIError(401, code, messages[code], clear_cookie=code != "SESSION_REQUIRED")


def authenticate(db: Session, token: str | None, clock: Clock) -> VisitorSession:
    if token is None:
        raise session_failure("SESSION_REQUIRED")
    if not TOKEN_PATTERN.fullmatch(token):
        raise session_failure("SESSION_INVALID")
    digest = hashlib.sha256(token.encode("ascii")).digest()
    row = db.execute(
        select(
            VisitorContext.visitor_context_id,
            VisitorContext.expires_at,
            VisitorContext.invalidated_at,
        ).where(VisitorContext.session_token_hash == digest)
    ).one_or_none()
    if row is None or row.invalidated_at is not None:
        raise session_failure("SESSION_INVALID")
    # Check after the query, so time spent waiting on PostgreSQL counts toward expiry.
    if row.expires_at <= clock():
        raise session_failure("SESSION_EXPIRED")
    return VisitorSession(visitor_context_id=row.visitor_context_id, expires_at=row.expires_at)


def resolve_visitor(request: Request, clock: Clock) -> VisitorSession:
    with Session(request.app.state.engine) as db, db.begin():
        return authenticate(db, get_session_token(request), clock)


def require_visitor(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> Iterator[VisitorSession]:
    visitor = resolve_visitor(request, clock)
    yield visitor
    # The function-scoped dependency rechecks before sending protected data.
    # Future write services must also authenticate inside their commit transaction.
    resolve_visitor(request, clock)


CurrentVisitor = Annotated[VisitorSession, Depends(require_visitor, scope="function")]


def clear_session_cookie(response: Response, policy: CookiePolicy = HTTPS_COOKIE_POLICY) -> None:
    response.delete_cookie(
        policy.name,
        path=policy.path,
        secure=policy.secure,
        httponly=policy.httponly,
        samesite=policy.samesite,
    )


@router.post(
    "/visitor-session",
    response_model=VisitorSession,
    status_code=201,
    responses={200: {"model": VisitorSession}},
)
def bootstrap_visitor(
    payload: VisitorSessionCreate,
    request: Request,
    response: Response,
    clock: Annotated[Clock, Depends(get_clock)],
) -> VisitorSession:
    policy = get_cookie_policy(request)
    token = get_session_token(request)
    new_token = None
    with Session(request.app.state.engine, expire_on_commit=False) as db, db.begin():
        try:
            visitor = authenticate(db, token, clock)
        except APIError:
            # This explicit bootstrap is the only place permitted to create a fresh owner.
            # Never register a supplied token, recover by UUID, or modify the old owner.
            new_token = secrets.token_urlsafe(32)
            created_at = clock()
            record = VisitorContext(
                session_token_hash=hashlib.sha256(new_token.encode("ascii")).digest(),
                created_at=created_at,
                expires_at=created_at
                + timedelta(seconds=request.app.state.settings.visitor_session_ttl_seconds),
            )
            db.add(record)
            db.flush()
            visitor = VisitorSession(
                visitor_context_id=record.visitor_context_id, expires_at=record.expires_at
            )
    # Reached only after commit. No cookie is issued for a rolled-back creation.
    if new_token is not None:
        remaining = int((visitor.expires_at - clock()).total_seconds())
        if remaining <= 0:
            raise session_failure("SESSION_EXPIRED")
        response.set_cookie(
            policy.name,
            new_token,
            max_age=remaining,
            expires=visitor.expires_at,
            path=policy.path,
            secure=policy.secure,
            httponly=policy.httponly,
            samesite=policy.samesite,
        )
    else:
        # Fresh query also sees invalidation/expiry during the bootstrap transaction.
        visitor = resolve_visitor(request, clock)
        response.status_code = 200
    return visitor
