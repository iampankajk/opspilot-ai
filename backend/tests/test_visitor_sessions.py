import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import VisitorContext
from app.visitor_sessions import (
    COOKIE_NAME,
    DEV_HTTP_COOKIE_NAME,
    TOKEN_PATTERN,
    CurrentVisitor,
    get_clock,
)

HEADERS = {"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"}


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now


@pytest.fixture
def context(database, monkeypatch):
    engine, settings = database
    with engine.connect() as connection:
        transaction = connection.begin()

        def scoped_session(*args, **kwargs):
            kwargs.pop("bind", None)
            return Session(bind=connection, join_transaction_mode="create_savepoint", **kwargs)

        monkeypatch.setattr("app.visitor_sessions.Session", scoped_session)
        app = create_app(settings)
        clock = Clock()
        app.dependency_overrides[get_clock] = lambda: clock

        @app.get("/test/current")
        def current(visitor: CurrentVisitor):
            return visitor

        @app.get("/test/expires-during-request")
        def expires_late(visitor: CurrentVisitor):
            clock.now += timedelta(days=2)
            return {"protected": "must not be sent after expiry"}

        with TestClient(app, base_url="https://localhost:3000") as client:
            yield client, connection, clock, app
        transaction.rollback()


def count_visitors(connection):
    return connection.scalar(select(func.count()).select_from(VisitorContext))


def bootstrap(client, payload=None):
    return client.post(
        "/api/v1/visitor-session", json={} if payload is None else payload, headers=HEADERS
    )


def assert_cleared(response):
    cookie = SimpleCookie(response.headers["set-cookie"])[COOKIE_NAME]
    assert cookie["max-age"] == "0"
    assert cookie["httponly"] and cookie["secure"]
    assert cookie["path"] == "/" and not cookie["domain"]
    assert cookie["samesite"] == "lax"


def test_bootstrap_commits_only_digest_and_sets_host_cookie(context, caplog):
    client, connection, clock, _ = context
    before = count_visitors(connection)
    response = bootstrap(client)
    assert response.status_code == 201
    assert set(response.json()) == {"visitor_context_id", "expires_at"}
    assert response.headers["cache-control"] == "no-store"
    UUID(response.headers["X-Request-ID"])
    cookie = SimpleCookie(response.headers["set-cookie"])[COOKIE_NAME]
    token = cookie.value
    token_shape_ok = (
        bool(TOKEN_PATTERN.fullmatch(token)) and len(base64.urlsafe_b64decode(token + "=")) == 32
    )
    assert token_shape_ok
    assert cookie["httponly"] and cookie["secure"]
    assert cookie["path"] == "/" and not cookie["domain"]
    assert cookie["samesite"] == "lax"
    assert int(cookie["max-age"]) == 86400
    with Session(bind=connection) as db:
        record = db.get(VisitorContext, UUID(response.json()["visitor_context_id"]))
        stored_hash_matches = secrets.compare_digest(
            record.session_token_hash, hashlib.sha256(token.encode()).digest()
        )
        assert stored_hash_matches
        assert record.expires_at - record.created_at == timedelta(hours=24)
        assert record.created_at == clock.now
    assert count_visitors(connection) == before + 1
    leaked = token in response.text or token in caplog.text
    assert not leaked


def test_existing_cookie_is_reused_without_rotation_or_sliding_expiry(context):
    client, connection, clock, _ = context
    first = bootstrap(client)
    before = count_visitors(connection)
    clock.now += timedelta(hours=3)
    second = bootstrap(client)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert "set-cookie" not in second.headers
    assert count_visitors(connection) == before
    assert client.get("/test/current").json() == first.json()


@pytest.mark.parametrize("token", ["", "invalid", "A" * 43, str(uuid4()), "x" * 44, "!" * 43])
def test_invalid_token_is_rejected_and_cleared_without_creating_visitor(context, token):
    client, connection, _, _ = context
    before = count_visitors(connection)
    response = client.get("/test/current", headers={"Cookie": f"{COOKIE_NAME}={token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"
    assert_cleared(response)
    assert count_visitors(connection) == before


def test_uuid_header_and_query_never_authenticate_a_missing_cookie(context):
    client, connection, _, _ = context
    owner = bootstrap(client).json()["visitor_context_id"]
    before = count_visitors(connection)
    client.cookies.clear()
    response = client.get(
        f"/test/current?visitor_context_id={owner}",
        headers={"visitor_context_id": owner, "X-Visitor-Context-ID": owner},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"
    assert count_visitors(connection) == before


def test_expired_token_stays_expired_and_explicit_bootstrap_gets_new_owner(context):
    client, connection, clock, _ = context
    first = bootstrap(client).json()
    clock.now += timedelta(hours=24)
    response = client.get("/test/current")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert_cleared(response)
    second = bootstrap(client)
    assert second.status_code == 201
    assert second.json()["visitor_context_id"] != first["visitor_context_id"]
    with Session(bind=connection) as db:
        assert db.get(VisitorContext, UUID(first["visitor_context_id"])) is not None


def test_expiry_is_rechecked_before_protected_response(context):
    client, _, _, _ = context
    bootstrap(client)
    response = client.get("/test/expires-during-request")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert "must not be sent" not in response.text


def test_invalidation_rejects_cookie_but_keeps_owner(context):
    client, connection, clock, _ = context
    owner = UUID(bootstrap(client).json()["visitor_context_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        db.get(VisitorContext, owner).invalidated_at = clock.now
    response = client.get("/test/current")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"
    assert_cleared(response)
    with Session(bind=connection) as db:
        assert db.get(VisitorContext, owner) is not None


@pytest.mark.parametrize(
    "payload", [{"visitor_context_id": str(uuid4())}, {"token": "attacker"}, [], "invalid"]
)
def test_bootstrap_rejects_identity_overrides_and_wrong_body(context, payload):
    client, connection, _, _ = context
    before = count_visitors(connection)
    response = bootstrap(client, payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "set-cookie" not in response.headers
    assert count_visitors(connection) == before


def test_bootstrap_empty_or_malformed_json_is_rejected(context):
    client, _, _, _ = context
    for body in ("", "null", "{"):
        response = client.post(
            "/api/v1/visitor-session",
            content=body,
            headers=HEADERS | {"Content-Type": "application/json"},
        )
        assert response.status_code == 422


def test_explicit_bootstrap_with_bad_cookie_never_registers_client_token(context):
    client, connection, _, _ = context
    response = client.post(
        "/api/v1/visitor-session",
        json={},
        headers=HEADERS | {"Cookie": f"{COOKIE_NAME}={'A' * 43}"},
    )
    assert response.status_code == 201
    with Session(bind=connection) as db:
        found = db.scalar(
            select(VisitorContext.visitor_context_id).where(
                VisitorContext.session_token_hash == hashlib.sha256(b"A" * 43).digest()
            )
        )
        assert found is None


def test_separate_cookie_jars_cannot_claim_each_others_public_ids(context):
    first, _, _, app = context
    a = bootstrap(first).json()["visitor_context_id"]
    with TestClient(app, base_url="https://localhost:3000") as second:
        b = bootstrap(second).json()["visitor_context_id"]
        assert a != b
        response = second.get(
            f"/test/current?visitor_context_id={a}", headers={"X-Visitor-Context-ID": a}
        )
        assert response.json()["visitor_context_id"] == b
        assert first.get(f"/test/current?visitor_context_id={b}").json()["visitor_context_id"] == a


def test_database_commit_failure_issues_no_cookie_and_is_retryable(context, caplog):
    client, connection, _, _ = context
    before = count_visitors(connection)

    def fail_commit(session):
        raise OperationalError("private SQL", {"private": "parameter"}, Exception("private error"))

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = bootstrap(client)
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["retryable"] is True
    assert "set-cookie" not in response.headers
    assert "private" not in response.text + caplog.text
    assert count_visitors(connection) == before
    assert bootstrap(client).status_code == 201


def test_ttl_configuration_does_not_extend_existing_records(context):
    client, _, clock, app = context
    first = bootstrap(client).json()
    app.state.settings = app.state.settings.model_copy(
        update={"visitor_session_ttl_seconds": 172800}
    )
    clock.now += timedelta(hours=23)
    assert bootstrap(client).json() == first
    clock.now += timedelta(hours=1)
    assert client.get("/test/current").status_code == 401
    new_session = bootstrap(client).json()
    expires = datetime.fromisoformat(new_session["expires_at"])
    assert expires - clock.now == timedelta(hours=48)


@pytest.mark.parametrize("ttl", [0, -1, "invalid"])
def test_bad_ttl_configuration_is_rejected(ttl):
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql+psycopg://localhost/unused", visitor_session_ttl_seconds=ttl
        )


def test_dev_http_cookie_policy_uses_non_host_non_secure_cookie_and_clears_it(
    database, monkeypatch
):
    engine, base_settings = database
    http_settings = Settings(
        database_url=base_settings.database_url,
        public_origin="http://localhost:3000",
        allow_insecure_local_http=True,
    )
    with engine.connect() as connection:
        transaction = connection.begin()

        def scoped_session(*args, **kwargs):
            kwargs.pop("bind", None)
            return Session(bind=connection, join_transaction_mode="create_savepoint", **kwargs)

        monkeypatch.setattr("app.visitor_sessions.Session", scoped_session)
        app = create_app(http_settings)
        clock = Clock()
        app.dependency_overrides[get_clock] = lambda: clock

        @app.get("/test/current")
        def current(visitor: CurrentVisitor):
            return visitor

        with TestClient(app, base_url="http://localhost:3000") as client:
            http_headers = {"Origin": "http://localhost:3000", "X-OpsPilot-Request": "1"}
            created = client.post("/api/v1/visitor-session", json={}, headers=http_headers)
            assert created.status_code == 201
            cookies = SimpleCookie(created.headers["set-cookie"])
            assert COOKIE_NAME not in cookies
            cookie = cookies[DEV_HTTP_COOKIE_NAME]
            assert cookie["httponly"] and not cookie["secure"]
            assert cookie["path"] == "/" and not cookie["domain"]
            assert cookie["samesite"] == "lax"

            current_resp = client.get("/test/current")
            assert current_resp.status_code == 200
            assert current_resp.json() == created.json()

            invalid = client.get(
                "/test/current", headers={"Cookie": f"{DEV_HTTP_COOKIE_NAME}=invalid"}
            )
            assert invalid.status_code == 401
            assert invalid.json()["error"]["code"] == "SESSION_INVALID"
            cleared = SimpleCookie(invalid.headers["set-cookie"])[DEV_HTTP_COOKIE_NAME]
            assert cleared["max-age"] == "0"
            assert cleared["httponly"] and not cleared["secure"]
            assert cleared["path"] == "/" and cleared["samesite"] == "lax"
        transaction.rollback()


def test_https_origin_retains_host_secure_cookie_even_when_dev_http_flag_is_set(context):
    client, _, _, app = context
    app.state.settings = app.state.settings.model_copy(update={"allow_insecure_local_http": True})
    response = bootstrap(client)
    assert response.status_code == 201
    cookie = SimpleCookie(response.headers["set-cookie"])[COOKIE_NAME]
    assert cookie["httponly"] and cookie["secure"]
