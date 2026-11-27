import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import field_validator
from sqlalchemy import select

from app import visitor_sessions
from app.api_errors import APIError
from app.models import ActorSession, VisitorContext, WorkspaceActor
from app.visitor_sessions import (
    ACTOR_REF_PATTERN,
    TOKEN_PATTERN,
    ActorRole,
    AuthSession,
    Clock,
    CurrentActor,
    authenticate_actor,
    authorize_role,
    clear_session_cookie,
    get_clock,
    get_cookie_policy,
    get_session_token,
    hash_secret,
    issue_session_cookie,
    require_actor_once,
    require_role,
    role_forbidden,
)
from app.workspace_schemas import Schema

router = APIRouter(prefix="/api/v1")

__all__ = [
    "ActorRole",
    "AuthSession",
    "CurrentActor",
    "authenticate_actor",
    "authorize_role",
    "require_role",
    "role_forbidden",
    "router",
]


class EmptyBody(Schema):
    pass


class ActorCredential(Schema):
    actor_id: UUID
    actor_ref: str
    display_name: str
    role: ActorRole
    access_code: str


class WorkspaceBootstrap(Schema):
    visitor_context_id: UUID
    expires_at: datetime
    current_session: AuthSession
    actor_credentials: list[ActorCredential]

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ActorLoginRequest(Schema):
    visitor_context_id: UUID
    actor_ref: str
    access_code: str


class LogoutResponse(Schema):
    logged_out: Literal[True] = True


def authentication_failed() -> APIError:
    return APIError(401, "AUTHENTICATION_FAILED", "Authentication failed.")


def no_query_overrides(request: Request) -> None:
    if request.query_params:
        raise APIError(
            422, "VALIDATION_ERROR", "Query overrides are not supported on this endpoint."
        )


@router.post("/auth/workspaces", response_model=WorkspaceBootstrap, status_code=201)
def create_workspace(
    payload: EmptyBody,
    request: Request,
    response: Response,
    clock: Annotated[Clock, Depends(get_clock)],
) -> WorkspaceBootstrap:
    no_query_overrides(request)
    policy = get_cookie_policy(request)
    engineer_code = secrets.token_urlsafe(32)
    lead_code = secrets.token_urlsafe(32)
    session_token = secrets.token_urlsafe(32)
    with (
        visitor_sessions.Session(request.app.state.engine, expire_on_commit=False) as db,
        db.begin(),
    ):
        created_at = clock()
        expires_at = created_at + timedelta(
            seconds=request.app.state.settings.visitor_session_ttl_seconds
        )
        workspace = VisitorContext(
            session_token_hash=None,
            created_at=created_at,
            expires_at=expires_at,
        )
        db.add(workspace)
        db.flush()

        engineer = WorkspaceActor(
            visitor_context_id=workspace.visitor_context_id,
            actor_ref="ops-engineer-1",
            display_name="Maya Lin",
            role="engineer",
            access_code_hash=hash_secret(engineer_code),
            created_at=created_at,
        )
        lead = WorkspaceActor(
            visitor_context_id=workspace.visitor_context_id,
            actor_ref="payments-lead-1",
            display_name="Devon Patel",
            role="lead",
            access_code_hash=hash_secret(lead_code),
            created_at=created_at,
        )
        db.add_all([engineer, lead])
        db.flush()

        session_row = ActorSession(
            visitor_context_id=workspace.visitor_context_id,
            actor_id=engineer.actor_id,
            session_token_hash=hash_secret(session_token),
            created_at=created_at,
            expires_at=expires_at,
        )
        db.add(session_row)
        db.flush()

        current_session = AuthSession(
            session_id=session_row.session_id,
            visitor_context_id=workspace.visitor_context_id,
            actor_id=engineer.actor_id,
            actor_ref=engineer.actor_ref,
            display_name=engineer.display_name,
            role="engineer",
            expires_at=expires_at,
        )
        bootstrap = WorkspaceBootstrap(
            visitor_context_id=workspace.visitor_context_id,
            expires_at=expires_at,
            current_session=current_session,
            actor_credentials=[
                ActorCredential(
                    actor_id=engineer.actor_id,
                    actor_ref=engineer.actor_ref,
                    display_name=engineer.display_name,
                    role="engineer",
                    access_code=engineer_code,
                ),
                ActorCredential(
                    actor_id=lead.actor_id,
                    actor_ref=lead.actor_ref,
                    display_name=lead.display_name,
                    role="lead",
                    access_code=lead_code,
                ),
            ],
        )
    # Reached only after commit. No cookie is issued for a rolled-back creation.
    issue_session_cookie(response, policy, session_token, expires_at, clock)
    return bootstrap


@router.post("/auth/login", response_model=AuthSession)
def login_actor(
    payload: ActorLoginRequest,
    request: Request,
    response: Response,
    clock: Annotated[Clock, Depends(get_clock)],
) -> AuthSession:
    no_query_overrides(request)
    if not ACTOR_REF_PATTERN.fullmatch(payload.actor_ref) or not TOKEN_PATTERN.fullmatch(
        payload.access_code
    ):
        raise authentication_failed()
    policy = get_cookie_policy(request)
    code_digest = hash_secret(payload.access_code)
    existing_token = get_session_token(request)
    new_token = secrets.token_urlsafe(32)
    with (
        visitor_sessions.Session(request.app.state.engine, expire_on_commit=False) as db,
        db.begin(),
    ):
        now = clock()
        row = db.execute(
            select(
                WorkspaceActor.actor_id,
                WorkspaceActor.visitor_context_id,
                WorkspaceActor.actor_ref,
                WorkspaceActor.display_name,
                WorkspaceActor.role,
                WorkspaceActor.access_code_hash,
                WorkspaceActor.disabled_at,
                VisitorContext.expires_at.label("workspace_expires_at"),
                VisitorContext.invalidated_at.label("workspace_invalidated_at"),
            )
            .join(
                VisitorContext,
                VisitorContext.visitor_context_id == WorkspaceActor.visitor_context_id,
            )
            .where(
                WorkspaceActor.visitor_context_id == payload.visitor_context_id,
                WorkspaceActor.actor_ref == payload.actor_ref,
                WorkspaceActor.access_code_hash.is_not(None),
            )
        ).one_or_none()
        if (
            row is None
            or row.disabled_at is not None
            or row.workspace_invalidated_at is not None
            or row.workspace_expires_at <= now
            or not secrets.compare_digest(row.access_code_hash, code_digest)
        ):
            raise authentication_failed()

        if existing_token is not None and TOKEN_PATTERN.fullmatch(existing_token):
            prior_session = db.scalar(
                select(ActorSession).where(
                    ActorSession.session_token_hash == hash_secret(existing_token)
                )
            )
            if prior_session is not None and prior_session.invalidated_at is None:
                prior_session.invalidated_at = max(now, prior_session.created_at)

        session_expires_at = min(
            now + timedelta(seconds=request.app.state.settings.visitor_session_ttl_seconds),
            row.workspace_expires_at,
        )
        session_row = ActorSession(
            visitor_context_id=row.visitor_context_id,
            actor_id=row.actor_id,
            session_token_hash=hash_secret(new_token),
            created_at=now,
            expires_at=session_expires_at,
        )
        db.add(session_row)
        db.flush()
        auth_session = AuthSession(
            session_id=session_row.session_id,
            visitor_context_id=row.visitor_context_id,
            actor_id=row.actor_id,
            actor_ref=row.actor_ref,
            display_name=row.display_name,
            role=row.role,
            expires_at=session_expires_at,
        )
    issue_session_cookie(response, policy, new_token, auth_session.expires_at, clock)
    return auth_session


@router.post("/auth/logout", response_model=LogoutResponse)
def logout_actor(
    payload: EmptyBody,
    request: Request,
    response: Response,
    actor: Annotated[AuthSession, Depends(require_actor_once)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LogoutResponse:
    no_query_overrides(request)
    token = get_session_token(request)
    with visitor_sessions.Session(request.app.state.engine) as db, db.begin():
        authed = authenticate_actor(db, token, clock)
        session_row = db.get(ActorSession, authed.session_id)
        if session_row is not None and session_row.invalidated_at is None:
            session_row.invalidated_at = max(clock(), session_row.created_at)
    clear_session_cookie(response, get_cookie_policy(request))
    return LogoutResponse()


@router.get("/auth/session", response_model=AuthSession)
def get_auth_session(
    request: Request,
    actor: CurrentActor,
) -> AuthSession:
    no_query_overrides(request)
    return actor
