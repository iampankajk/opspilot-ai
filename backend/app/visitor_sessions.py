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
from app.models import ActorSession, VisitorContext, WorkspaceActor

COOKIE_NAME = "__Host-opspilot_visitor"
DEV_HTTP_COOKIE_NAME = "opspilot_visitor"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}", flags=re.ASCII)
ACTOR_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$", flags=re.ASCII)
ActorRole = Literal["engineer", "lead"]
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


def hash_secret(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


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


class AuthSession(BaseModel):
    model_config = ConfigDict(frozen=True)
    session_id: UUID
    visitor_context_id: UUID
    actor_id: UUID
    actor_ref: str
    display_name: str
    role: ActorRole
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


def role_forbidden() -> APIError:
    return APIError(
        403,
        "ROLE_FORBIDDEN",
        "You do not have permission to perform this action.",
    )


def authorize_role(actor: AuthSession, *allowed_roles: ActorRole) -> AuthSession:
    if actor.role not in allowed_roles:
        raise role_forbidden()
    return actor


def authenticate_actor(db: Session, token: str | None, clock: Clock) -> AuthSession:
    if token is None:
        raise session_failure("SESSION_REQUIRED")
    if not TOKEN_PATTERN.fullmatch(token):
        raise session_failure("SESSION_INVALID")
    digest = hash_secret(token)
    row = db.execute(
        select(
            ActorSession.session_id,
            ActorSession.visitor_context_id,
            ActorSession.actor_id,
            ActorSession.expires_at.label("session_expires_at"),
            ActorSession.invalidated_at.label("session_invalidated_at"),
            WorkspaceActor.actor_ref,
            WorkspaceActor.display_name,
            WorkspaceActor.role,
            WorkspaceActor.disabled_at.label("actor_disabled_at"),
            VisitorContext.expires_at.label("workspace_expires_at"),
            VisitorContext.invalidated_at.label("workspace_invalidated_at"),
        )
        .join(
            WorkspaceActor,
            (WorkspaceActor.visitor_context_id == ActorSession.visitor_context_id)
            & (WorkspaceActor.actor_id == ActorSession.actor_id),
        )
        .join(
            VisitorContext,
            VisitorContext.visitor_context_id == ActorSession.visitor_context_id,
        )
        .where(ActorSession.session_token_hash == digest)
    ).one_or_none()
    if (
        row is None
        or row.session_invalidated_at is not None
        or row.actor_disabled_at is not None
        or row.workspace_invalidated_at is not None
    ):
        raise session_failure("SESSION_INVALID")
    # Check after the query, so time spent waiting on PostgreSQL counts toward expiry.
    now = clock()
    if row.session_expires_at <= now or row.workspace_expires_at <= now:
        raise session_failure("SESSION_EXPIRED")
    return AuthSession(
        session_id=row.session_id,
        visitor_context_id=row.visitor_context_id,
        actor_id=row.actor_id,
        actor_ref=row.actor_ref,
        display_name=row.display_name,
        role=row.role,
        expires_at=min(row.session_expires_at, row.workspace_expires_at),
    )


def authenticate(db: Session, token: str | None, clock: Clock) -> VisitorSession:
    auth = authenticate_actor(db, token, clock)
    return VisitorSession(visitor_context_id=auth.visitor_context_id, expires_at=auth.expires_at)


def resolve_actor(request: Request, clock: Clock) -> AuthSession:
    with Session(request.app.state.engine) as db, db.begin():
        return authenticate_actor(db, get_session_token(request), clock)


def resolve_visitor(request: Request, clock: Clock) -> VisitorSession:
    auth = resolve_actor(request, clock)
    return VisitorSession(visitor_context_id=auth.visitor_context_id, expires_at=auth.expires_at)


def require_actor(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> Iterator[AuthSession]:
    actor = resolve_actor(request, clock)
    yield actor
    # The function-scoped dependency rechecks before sending protected data.
    # Write services must also authenticate inside their commit transaction.
    resolve_actor(request, clock)


def require_actor_once(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> AuthSession:
    return resolve_actor(request, clock)


def require_visitor(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> Iterator[VisitorSession]:
    visitor = resolve_visitor(request, clock)
    yield visitor
    resolve_visitor(request, clock)


CurrentActor = Annotated[AuthSession, Depends(require_actor, scope="function")]
CurrentVisitor = Annotated[VisitorSession, Depends(require_visitor, scope="function")]


def require_role(*allowed_roles: ActorRole):
    if not allowed_roles:
        raise ValueError("At least one role must be specified")

    def dependency(
        request: Request,
        clock: Annotated[Clock, Depends(get_clock)],
    ) -> Iterator[AuthSession]:
        actor = resolve_actor(request, clock)
        authorize_role(actor, *allowed_roles)
        yield actor
        rechecked = resolve_actor(request, clock)
        authorize_role(rechecked, *allowed_roles)

    return dependency


def issue_session_cookie(
    response: Response,
    policy: CookiePolicy,
    token: str,
    expires_at: datetime,
    clock: Clock,
) -> None:
    remaining = int((expires_at - clock()).total_seconds())
    if remaining <= 0:
        raise session_failure("SESSION_EXPIRED")
    response.set_cookie(
        policy.name,
        token,
        max_age=remaining,
        expires=expires_at,
        path=policy.path,
        secure=policy.secure,
        httponly=policy.httponly,
        samesite=policy.samesite,
    )


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
            # This explicit bootstrap is the only place permitted to create a fresh legacy owner.
            # Never register a supplied token, recover by UUID, or grant Lead access.
            new_token = secrets.token_urlsafe(32)
            digest = hash_secret(new_token)
            created_at = clock()
            expires_at = created_at + timedelta(
                seconds=request.app.state.settings.visitor_session_ttl_seconds
            )
            record = VisitorContext(
                session_token_hash=digest,
                created_at=created_at,
                expires_at=expires_at,
            )
            db.add(record)
            db.flush()
            engineer = WorkspaceActor(
                visitor_context_id=record.visitor_context_id,
                actor_ref="ops-engineer-1",
                display_name="Maya Lin",
                role="engineer",
                access_code_hash=None,
                created_at=created_at,
            )
            db.add(engineer)
            db.flush()
            db.add(
                ActorSession(
                    visitor_context_id=record.visitor_context_id,
                    actor_id=engineer.actor_id,
                    session_token_hash=digest,
                    created_at=created_at,
                    expires_at=expires_at,
                )
            )
            visitor = VisitorSession(
                visitor_context_id=record.visitor_context_id, expires_at=record.expires_at
            )
    # Reached only after commit. No cookie is issued for a rolled-back creation.
    if new_token is not None:
        issue_session_cookie(response, policy, new_token, visitor.expires_at, clock)
    else:
        # Fresh query also sees invalidation/expiry during the bootstrap transaction.
        visitor = resolve_visitor(request, clock)
        response.status_code = 200
    return visitor
