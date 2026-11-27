"""Task 6A acceptance and security tests for actor identity and role boundaries."""

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.actor_auth import AuthSession, CurrentActor, require_role
from app.config import Settings
from app.findings_provider import MockFindingsProvider
from app.main import create_app
from app.models import ActorSession, AIGenerationRequest, VisitorContext, WorkspaceActor
from app.visitor_sessions import (
    COOKIE_NAME,
    DEV_HTTP_COOKIE_NAME,
    TOKEN_PATTERN,
    get_clock,
)

HEADERS = {"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"}
INCIDENT_URL = "/api/v1/incidents/INC-2026-1042"


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now


@pytest.fixture
def auth_context(database, monkeypatch):
    engine, settings = database
    with engine.connect() as connection:
        transaction = connection.begin()

        def scoped_session(*args, **kwargs):
            kwargs.pop("bind", None)
            return Session(bind=connection, join_transaction_mode="create_savepoint", **kwargs)

        monkeypatch.setattr("app.visitor_sessions.Session", scoped_session)
        monkeypatch.setattr("app.investigations.Session", scoped_session)
        monkeypatch.setattr("app.evidence.Session", scoped_session)
        monkeypatch.setattr("app.findings.Session", scoped_session)

        app = create_app(settings.model_copy(update={"ai_findings_enabled": True}))
        clock = Clock()
        app.dependency_overrides[get_clock] = lambda: clock

        @app.get("/test/lead-only")
        def lead_only(actor: Annotated[AuthSession, Depends(require_role("lead"))]):
            return {"actor_id": str(actor.actor_id), "role": actor.role}

        @app.get("/test/expires-during-request")
        def expires_during_request(actor: CurrentActor):
            clock.now += timedelta(days=2)
            return {"secret": "must-not-leak"}

        with TestClient(app, base_url="https://localhost:3000") as client:
            app.state.findings_provider = MockFindingsProvider()
            yield client, connection, clock, app
        transaction.rollback()


def bootstrap_workspace(client, payload=None):
    return client.post(
        "/api/v1/auth/workspaces",
        json={} if payload is None else payload,
        headers=HEADERS,
    )


def login_actor(client, visitor_context_id, actor_ref, access_code, **extra):
    return client.post(
        "/api/v1/auth/login",
        json={
            "visitor_context_id": str(visitor_context_id),
            "actor_ref": actor_ref,
            "access_code": access_code,
        }
        | extra,
        headers=HEADERS,
    )


def assert_cookie_cleared(response, cookie_name=COOKIE_NAME, *, secure=True):
    cookie = SimpleCookie(response.headers["set-cookie"])[cookie_name]
    assert cookie["max-age"] == "0"
    assert cookie["httponly"]
    assert bool(cookie["secure"]) is secure
    assert cookie["path"] == "/" and not cookie["domain"]
    assert cookie["samesite"] == "lax"


def test_workspace_bootstrap_stores_only_digests_and_sets_engineer_cookie(auth_context, caplog):
    client, connection, clock, _ = auth_context
    with caplog.at_level(logging.DEBUG):
        resp = bootstrap_workspace(client)
    assert resp.status_code == 201
    assert resp.headers["cache-control"] == "no-store"
    UUID(resp.headers["X-Request-ID"])

    body = resp.json()
    assert set(body) == {
        "visitor_context_id",
        "expires_at",
        "current_session",
        "actor_credentials",
    }
    session_info = body["current_session"]
    assert session_info["actor_ref"] == "ops-engineer-1"
    assert session_info["display_name"] == "Maya Lin"
    assert session_info["role"] == "engineer"
    assert session_info["visitor_context_id"] == body["visitor_context_id"]

    creds = {item["actor_ref"]: item for item in body["actor_credentials"]}
    assert set(creds) == {"ops-engineer-1", "payments-lead-1"}
    assert creds["ops-engineer-1"]["role"] == "engineer"
    assert creds["ops-engineer-1"]["display_name"] == "Maya Lin"
    assert creds["payments-lead-1"]["role"] == "lead"
    assert creds["payments-lead-1"]["display_name"] == "Devon Patel"

    cookie = SimpleCookie(resp.headers["set-cookie"])[COOKIE_NAME]
    session_token = cookie.value
    assert TOKEN_PATTERN.fullmatch(session_token)
    assert len(base64.urlsafe_b64decode(session_token + "=")) == 32
    assert cookie["httponly"] and cookie["secure"]
    assert cookie["path"] == "/" and not cookie["domain"]
    assert cookie["samesite"] == "lax"

    eng_code = creds["ops-engineer-1"]["access_code"]
    lead_code = creds["payments-lead-1"]["access_code"]
    assert eng_code != lead_code
    assert TOKEN_PATTERN.fullmatch(eng_code)
    assert TOKEN_PATTERN.fullmatch(lead_code)

    ws_id = UUID(body["visitor_context_id"])
    with Session(bind=connection) as db:
        vc = db.get(VisitorContext, ws_id)
        assert vc is not None
        assert vc.session_token_hash is None
        assert vc.created_at == clock.now
        assert vc.expires_at == clock.now + timedelta(hours=24)

        actors = db.scalars(
            select(WorkspaceActor).where(WorkspaceActor.visitor_context_id == ws_id)
        ).all()
        assert len(actors) == 2
        by_ref = {a.actor_ref: a for a in actors}
        assert secrets.compare_digest(
            by_ref["ops-engineer-1"].access_code_hash,
            hashlib.sha256(eng_code.encode("ascii")).digest(),
        )
        assert secrets.compare_digest(
            by_ref["payments-lead-1"].access_code_hash,
            hashlib.sha256(lead_code.encode("ascii")).digest(),
        )

        sessions = db.scalars(
            select(ActorSession).where(ActorSession.visitor_context_id == ws_id)
        ).all()
        assert len(sessions) == 1
        assert sessions[0].actor_id == by_ref["ops-engineer-1"].actor_id
        assert secrets.compare_digest(
            sessions[0].session_token_hash,
            hashlib.sha256(session_token.encode("ascii")).digest(),
        )

    assert session_token not in resp.text
    for secret_val in (session_token, eng_code, lead_code):
        assert secret_val not in caplog.text


def test_bootstrap_with_existing_cookie_creates_separate_empty_workspace_without_leaking_prior(
    auth_context,
):
    client, _, _, _ = auth_context
    first = bootstrap_workspace(client).json()
    first_ws = first["visitor_context_id"]
    first_lead_code = next(
        c["access_code"] for c in first["actor_credentials"] if c["role"] == "lead"
    )
    inc_id = client.get(INCIDENT_URL).json()["incident"]["incident_id"]
    assert (
        client.post(
            "/api/v1/investigations", json={"incident_id": inc_id}, headers=HEADERS
        ).status_code
        == 201
    )

    second = bootstrap_workspace(client)
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["visitor_context_id"] != first_ws
    assert first_lead_code not in second.text
    assert client.get("/api/v1/investigations").json() == {"investigations": []}


def test_multi_actor_shared_investigation_discovery_and_inspection(auth_context, caplog):
    eng_client, _, _, app = auth_context
    boot = bootstrap_workspace(eng_client).json()
    ws_id = boot["visitor_context_id"]
    lead_cred = next(c for c in boot["actor_credentials"] if c["role"] == "lead")

    incident = eng_client.get(INCIDENT_URL).json()["incident"]
    created = eng_client.post(
        "/api/v1/investigations", json={"incident_id": incident["incident_id"]}, headers=HEADERS
    )
    assert created.status_code == 201
    ws = created.json()

    # Engineer retrieves evidence and generates AI findings.
    ev = eng_client.post(
        f"/api/v1/investigations/{ws['investigation_id']}/threads/payment_failures/cases/case-failure-001/evidence-requests",
        json={"state_id": ws["state_id"], "expected_draft_version": ws["draft_version"]},
        headers=HEADERS,
    )
    assert ev.status_code == 200
    gen = eng_client.post(
        f"/api/v1/investigations/{ws['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
        json={
            "state_id": ws["state_id"],
            "expected_draft_version": ev.json()["draft_version"],
            "evidence_request_id": ev.json()["evidence_request_id"],
        },
        headers=HEADERS,
    )
    assert gen.status_code == 201

    with (
        caplog.at_level(logging.DEBUG),
        TestClient(app, base_url="https://localhost:3000") as lead_client,
    ):
        login = login_actor(lead_client, ws_id, "payments-lead-1", lead_cred["access_code"])
        assert login.status_code == 200
        lead_session = login.json()
        assert lead_session["role"] == "lead"
        assert lead_session["actor_ref"] == "payments-lead-1"
        assert lead_session["visitor_context_id"] == ws_id
        lead_cookie = SimpleCookie(login.headers["set-cookie"])[COOKIE_NAME].value
        assert lead_cred["access_code"] not in login.text
        assert lead_cookie not in login.text
        assert lead_cred["access_code"] not in caplog.text
        assert lead_cookie not in caplog.text

        # Lead discovers investigation via GET /api/v1/investigations.
        listed = lead_client.get("/api/v1/investigations")
        assert listed.status_code == 200
        items = listed.json()["investigations"]
        assert len(items) == 1
        assert items[0]["investigation_id"] == ws["investigation_id"]
        assert items[0]["incident_id"] == incident["incident_id"]
        assert items[0]["incident_ref"] == "INC-2026-1042"
        assert items[0]["state_id"] == ws["state_id"]
        assert items[0]["draft_version"] >= 1
        assert items[0]["created_at"].endswith("Z") or "+" in items[0]["created_at"]

        # Lead can inspect workspace, cases, evidence, and stored findings.
        assert (
            lead_client.get(
                f"/api/v1/investigations/{ws['investigation_id']}/workspace"
            ).status_code
            == 200
        )
        assert (
            lead_client.get(
                f"/api/v1/investigations/{ws['investigation_id']}/threads/payment_failures/cases",
                params={"state_id": ws["state_id"]},
            ).status_code
            == 200
        )
        lead_ev = lead_client.post(
            f"/api/v1/investigations/{ws['investigation_id']}/threads/payment_failures/cases/case-failure-001/evidence-requests",
            json={
                "state_id": ws["state_id"],
                "expected_draft_version": items[0]["draft_version"],
            },
            headers=HEADERS,
        )
        assert lead_ev.status_code == 200
        lead_findings = lead_client.get(
            f"/api/v1/investigations/{ws['investigation_id']}/threads/payment_failures/cases/case-failure-001/findings",
            params={"state_id": ws["state_id"]},
        )
        assert lead_findings.status_code == 200
        assert len(lead_findings.json()["findings"]) >= 1

        # Engineer session in eng_client remains valid and independent.
        eng_check = eng_client.get("/api/v1/auth/session")
        assert eng_check.status_code == 200
        assert eng_check.json()["role"] == "engineer"


def test_authorization_401_403_404_matrix_and_precedence(auth_context):
    w1_eng, _, _, app = auth_context
    w1_boot = bootstrap_workspace(w1_eng).json()
    w1_ws = w1_boot["visitor_context_id"]
    w1_lead_code = next(
        c["access_code"] for c in w1_boot["actor_credentials"] if c["role"] == "lead"
    )
    incident_id = w1_eng.get(INCIDENT_URL).json()["incident"]["incident_id"]
    w1_inv = w1_eng.post(
        "/api/v1/investigations", json={"incident_id": incident_id}, headers=HEADERS
    ).json()
    w1_ev = w1_eng.post(
        f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/evidence-requests",
        json={"state_id": w1_inv["state_id"], "expected_draft_version": w1_inv["draft_version"]},
        headers=HEADERS,
    ).json()

    with (
        TestClient(app, base_url="https://localhost:3000") as anon,
        TestClient(app, base_url="https://localhost:3000") as w1_lead,
        TestClient(app, base_url="https://localhost:3000") as w2_eng,
        TestClient(app, base_url="https://localhost:3000") as w2_lead,
    ):
        assert login_actor(w1_lead, w1_ws, "payments-lead-1", w1_lead_code).status_code == 200
        w2_boot = bootstrap_workspace(w2_eng).json()
        w2_lead_code = next(
            c["access_code"] for c in w2_boot["actor_credentials"] if c["role"] == "lead"
        )
        assert (
            login_actor(
                w2_lead, w2_boot["visitor_context_id"], "payments-lead-1", w2_lead_code
            ).status_code
            == 200
        )

        # 1. Unauthenticated 401 checks.
        for method, path, body in [
            ("GET", "/api/v1/auth/session", None),
            ("POST", "/api/v1/auth/logout", {}),
            ("GET", "/api/v1/investigations", None),
            ("GET", INCIDENT_URL, None),
            ("POST", "/api/v1/investigations", {"incident_id": incident_id}),
            ("GET", f"/api/v1/investigations/{w1_inv['investigation_id']}/workspace", None),
            (
                "POST",
                f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
                {
                    "state_id": w1_inv["state_id"],
                    "expected_draft_version": w1_ev["draft_version"],
                    "evidence_request_id": w1_ev["evidence_request_id"],
                },
            ),
            ("GET", "/test/lead-only", None),
        ]:
            resp = (
                anon.get(path) if method == "GET" else anon.post(path, json=body, headers=HEADERS)
            )
            assert resp.status_code == 401, (method, path, resp.text)
            assert resp.json()["error"]["code"] == "SESSION_REQUIRED"

        # 2. Foreign-workspace Engineer AND Lead probing W1 receive 404 NOT_FOUND (never 403).
        for probe in (w2_eng, w2_lead):
            assert (
                probe.get(
                    f"/api/v1/investigations/{w1_inv['investigation_id']}/workspace"
                ).status_code
                == 404
            )
            assert (
                probe.get(
                    f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases",
                    params={"state_id": w1_inv["state_id"]},
                ).status_code
                == 404
            )
            assert (
                probe.post(
                    f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/evidence-requests",
                    json={
                        "state_id": w1_inv["state_id"],
                        "expected_draft_version": w1_ev["draft_version"],
                    },
                    headers=HEADERS,
                ).status_code
                == 404
            )
            fg_probe = probe.post(
                f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
                json={
                    "state_id": w1_inv["state_id"],
                    "expected_draft_version": w1_ev["draft_version"],
                    "evidence_request_id": w1_ev["evidence_request_id"],
                },
                headers=HEADERS,
            )
            assert fg_probe.status_code == 404
            assert fg_probe.json()["error"]["code"] == "NOT_FOUND"
            assert (
                probe.get(
                    f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/findings",
                    params={"state_id": w1_inv["state_id"]},
                ).status_code
                == 404
            )
            # W2 has no investigations of its own yet.
            assert probe.get("/api/v1/investigations").json() == {"investigations": []}

        # 3. Same-workspace Lead receives 403 ROLE_FORBIDDEN on Engineer-only routes.
        lead_create = w1_lead.post(
            "/api/v1/investigations", json={"incident_id": incident_id}, headers=HEADERS
        )
        assert lead_create.status_code == 403
        assert lead_create.json()["error"]["code"] == "ROLE_FORBIDDEN"

        lead_gen = w1_lead.post(
            f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
            json={
                "state_id": w1_inv["state_id"],
                "expected_draft_version": w1_ev["draft_version"],
                "evidence_request_id": w1_ev["evidence_request_id"],
            },
            headers=HEADERS,
        )
        assert lead_gen.status_code == 403
        assert lead_gen.json()["error"]["code"] == "ROLE_FORBIDDEN"

        # 422 precedes 403 on malformed payload, while 403 precedes 409 stale state.
        lead_bad_body = w1_lead.post(
            "/api/v1/investigations", json={"incident_id": "not-a-uuid"}, headers=HEADERS
        )
        assert lead_bad_body.status_code == 422
        lead_stale_state = w1_lead.post(
            f"/api/v1/investigations/{w1_inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
            json={
                "state_id": str(uuid4()),
                "expected_draft_version": 0,
                "evidence_request_id": str(uuid4()),
            },
            headers=HEADERS,
        )
        assert lead_stale_state.status_code == 403

        # 4. Same-workspace Engineer receives 403 ROLE_FORBIDDEN on Lead-guarded dependency route.
        eng_lead_route = w1_eng.get("/test/lead-only")
        assert eng_lead_route.status_code == 403
        assert eng_lead_route.json()["error"]["code"] == "ROLE_FORBIDDEN"
        assert w1_lead.get("/test/lead-only").status_code == 200


def test_anti_impersonation_escalation_and_uniform_login_failures(auth_context):
    client, connection, clock, app = auth_context
    boot = bootstrap_workspace(client).json()
    ws_id = UUID(boot["visitor_context_id"])
    lead_cred = next(c for c in boot["actor_credentials"] if c["role"] == "lead")
    eng_cred = next(c for c in boot["actor_credentials"] if c["role"] == "engineer")

    # Headers cannot spoof role or workspace.
    spoof_headers = {
        "X-Actor-Role": "lead",
        "X-Actor-Id": lead_cred["actor_id"],
        "X-Visitor-Context-ID": str(uuid4()),
    }
    session_resp = client.get("/api/v1/auth/session", headers=spoof_headers)
    assert session_resp.status_code == 200
    assert session_resp.json()["role"] == "engineer"
    assert session_resp.json()["actor_id"] == eng_cred["actor_id"]
    assert client.get("/test/lead-only", headers=spoof_headers).status_code == 403

    # Query and body overrides are rejected with 422.
    assert client.get("/api/v1/auth/session?role=lead").status_code == 422
    assert client.get("/api/v1/investigations?visitor_context_id=" + str(ws_id)).status_code == 422
    assert bootstrap_workspace(client, {"role": "lead"}).status_code == 422
    assert (
        login_actor(
            client, ws_id, "payments-lead-1", lead_cred["access_code"], role="lead"
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/auth/logout", json={"actor_id": lead_cred["actor_id"]}, headers=HEADERS
        ).status_code
        == 422
    )

    # Uniform 401 AUTHENTICATION_FAILED on bad credentials or disabled actor.
    with Session(bind=connection) as db:
        lead_row = db.get(WorkspaceActor, UUID(lead_cred["actor_id"]))
        lead_hash_hex = lead_row.access_code_hash.hex()

    with TestClient(app, base_url="https://localhost:3000") as other:
        for bad_ws, bad_ref, bad_code in [
            (ws_id, "payments-lead-1", "wrong-code"),
            (ws_id, "payments-lead-1", "A" * 43),
            (ws_id, "payments-lead-1", lead_hash_hex),
            (ws_id, "unknown-actor", lead_cred["access_code"]),
            (uuid4(), "payments-lead-1", lead_cred["access_code"]),
            (ws_id, "payments-lead-1", eng_cred["access_code"]),
        ]:
            fail = login_actor(other, bad_ws, bad_ref, bad_code)
            assert fail.status_code == 401
            assert fail.json()["error"]["code"] == "AUTHENTICATION_FAILED"
            assert "set-cookie" not in fail.headers

        # Disabled actor cannot log in.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
            db.get(WorkspaceActor, UUID(lead_cred["actor_id"])).disabled_at = clock.now
        disabled_login = login_actor(other, ws_id, "payments-lead-1", lead_cred["access_code"])
        assert disabled_login.status_code == 401
        assert disabled_login.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_legacy_visitor_session_is_engineer_only_and_cannot_login_as_lead(auth_context):
    client, connection, _, app = auth_context
    legacy = client.post("/api/v1/visitor-session", json={}, headers=HEADERS)
    assert legacy.status_code == 201
    ws_id = UUID(legacy.json()["visitor_context_id"])

    with Session(bind=connection) as db:
        actors = db.scalars(
            select(WorkspaceActor).where(WorkspaceActor.visitor_context_id == ws_id)
        ).all()
        assert len(actors) == 1
        assert actors[0].role == "engineer"
        assert actors[0].actor_ref == "ops-engineer-1"
        assert actors[0].access_code_hash is None

    session_resp = client.get("/api/v1/auth/session")
    assert session_resp.status_code == 200
    assert session_resp.json()["role"] == "engineer"
    assert client.get("/test/lead-only").status_code == 403

    with TestClient(app, base_url="https://localhost:3000") as second:
        assert login_actor(second, ws_id, "payments-lead-1", "A" * 43).status_code == 401
        assert login_actor(second, ws_id, "ops-engineer-1", "A" * 43).status_code == 401


def test_logout_invalidation_expiry_cap_and_session_hygiene(auth_context):
    eng_client, connection, clock, app = auth_context
    boot = bootstrap_workspace(eng_client).json()
    ws_id = UUID(boot["visitor_context_id"])
    lead_cred = next(c for c in boot["actor_credentials"] if c["role"] == "lead")
    eng_cred = next(c for c in boot["actor_credentials"] if c["role"] == "engineer")

    with TestClient(app, base_url="https://localhost:3000") as lead_client:
        # Advance 20h, then log in as Lead -> session expires at workspace deadline (+4h, not +24h).
        clock.now += timedelta(hours=20)
        lead_login = login_actor(lead_client, ws_id, "payments-lead-1", lead_cred["access_code"])
        assert lead_login.status_code == 200
        assert datetime.fromisoformat(lead_login.json()["expires_at"]) == clock.now + timedelta(
            hours=4
        )
        lead_cookie = SimpleCookie(lead_login.headers["set-cookie"])[COOKIE_NAME].value

        # Logout invalidates only Lead's session and clears cookie; Engineer stays active.
        logout_resp = lead_client.post("/api/v1/auth/logout", json={}, headers=HEADERS)
        assert logout_resp.status_code == 200
        assert logout_resp.json() == {"logged_out": True}
        assert_cookie_cleared(logout_resp)
        assert eng_client.get("/api/v1/auth/session").status_code == 200

        # Replaying logged-out Lead cookie returns 401 SESSION_INVALID and clears cookie.
        with TestClient(app, base_url="https://localhost:3000") as probe:
            replay = probe.get(
                "/api/v1/auth/session", headers={"Cookie": f"{COOKIE_NAME}={lead_cookie}"}
            )
            assert replay.status_code == 401
            assert replay.json()["error"]["code"] == "SESSION_INVALID"
            assert_cookie_cleared(replay)

        # Login while holding an existing valid session replaces only that caller's prior session.
        second_login = login_actor(lead_client, ws_id, "payments-lead-1", lead_cred["access_code"])
        assert second_login.status_code == 200
        first_lead_cookie = SimpleCookie(second_login.headers["set-cookie"])[COOKIE_NAME].value
        replaced_login = login_actor(
            lead_client, ws_id, "payments-lead-1", lead_cred["access_code"]
        )
        assert replaced_login.status_code == 200
        with TestClient(app, base_url="https://localhost:3000") as probe:
            assert (
                probe.get(
                    "/api/v1/auth/session", headers={"Cookie": f"{COOKIE_NAME}={first_lead_cookie}"}
                ).status_code
                == 401
            )
        assert eng_client.get("/api/v1/auth/session").status_code == 200

        # Disabling Engineer actor invalidates Engineer only; Lead stays active.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
            db.get(WorkspaceActor, UUID(eng_cred["actor_id"])).disabled_at = clock.now
        eng_disabled = eng_client.get("/api/v1/auth/session")
        assert eng_disabled.status_code == 401
        assert eng_disabled.json()["error"]["code"] == "SESSION_INVALID"
        assert_cookie_cleared(eng_disabled)
        assert lead_client.get("/api/v1/auth/session").status_code == 200

        # At workspace deadline (24h total), Lead's session expires.
        clock.now += timedelta(hours=4)
        lead_expired = lead_client.get("/api/v1/auth/session")
        assert lead_expired.status_code == 401
        assert lead_expired.json()["error"]["code"] == "SESSION_EXPIRED"
        assert_cookie_cleared(lead_expired)


def test_expiry_recheck_before_protected_response_and_post_csrf_middleware(auth_context):
    client, _, _, _ = auth_context
    bootstrap_workspace(client)
    resp = client.get("/test/expires-during-request")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "SESSION_EXPIRED"
    assert "must-not-leak" not in resp.text

    # POST /auth/workspaces and /auth/login enforce Origin and X-OpsPilot-Request.
    assert client.post("/api/v1/auth/workspaces", json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"visitor_context_id": str(uuid4()), "actor_ref": "a", "access_code": "b"},
            headers={"Origin": "https://other.test", "X-OpsPilot-Request": "1"},
        ).status_code
        == 403
    )


def test_secret_hygiene_in_errors_and_ordinary_responses(auth_context, caplog):
    client, _, _, _ = auth_context
    boot = bootstrap_workspace(client).json()
    eng_code = next(c["access_code"] for c in boot["actor_credentials"] if c["role"] == "engineer")
    lead_code = next(c["access_code"] for c in boot["actor_credentials"] if c["role"] == "lead")
    ws_id = boot["visitor_context_id"]

    with caplog.at_level(logging.DEBUG):
        bad_login = login_actor(client, ws_id, "payments-lead-1", lead_code, extra="bad")
        assert bad_login.status_code == 422
        assert lead_code not in bad_login.text
        assert eng_code not in client.get("/api/v1/auth/session").text
        assert lead_code not in client.get("/api/v1/investigations").text
        assert lead_code not in caplog.text
        assert eng_code not in caplog.text


def test_local_http_cookie_policy_for_auth_endpoints(database, monkeypatch):
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
        http_headers = {"Origin": "http://localhost:3000", "X-OpsPilot-Request": "1"}

        with TestClient(app, base_url="http://localhost:3000") as client:
            boot = client.post("/api/v1/auth/workspaces", json={}, headers=http_headers)
            assert boot.status_code == 201
            cookies = SimpleCookie(boot.headers["set-cookie"])
            assert COOKIE_NAME not in cookies
            cookie = cookies[DEV_HTTP_COOKIE_NAME]
            assert cookie["httponly"] and not cookie["secure"]
            assert cookie["path"] == "/" and not cookie["domain"]
            assert cookie["samesite"] == "lax"

            lead_cred = next(c for c in boot.json()["actor_credentials"] if c["role"] == "lead")
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "visitor_context_id": boot.json()["visitor_context_id"],
                    "actor_ref": "payments-lead-1",
                    "access_code": lead_cred["access_code"],
                },
                headers=http_headers,
            )
            assert login.status_code == 200
            login_cookie = SimpleCookie(login.headers["set-cookie"])[DEV_HTTP_COOKIE_NAME]
            assert login_cookie["httponly"] and not login_cookie["secure"]

            logout = client.post("/api/v1/auth/logout", json={}, headers=http_headers)
            assert logout.status_code == 200
            assert_cookie_cleared(logout, cookie_name=DEV_HTTP_COOKIE_NAME, secure=False)
        transaction.rollback()


def test_actor_and_session_db_constraints(database):
    engine, _ = database
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            now = datetime.now(UTC)
            vc1 = VisitorContext(
                session_token_hash=None, created_at=now, expires_at=now + timedelta(hours=24)
            )
            vc2 = VisitorContext(
                session_token_hash=None, created_at=now, expires_at=now + timedelta(hours=24)
            )
            db.add_all([vc1, vc2])
            db.flush()

            a1 = WorkspaceActor(
                visitor_context_id=vc1.visitor_context_id,
                actor_ref="ops-engineer-1",
                display_name="Maya Lin",
                role="engineer",
                access_code_hash=hashlib.sha256(b"code-1").digest(),
                created_at=now,
            )
            a2 = WorkspaceActor(
                visitor_context_id=vc2.visitor_context_id,
                actor_ref="payments-lead-1",
                display_name="Devon Patel",
                role="lead",
                access_code_hash=hashlib.sha256(b"code-2").digest(),
                created_at=now,
            )
            db.add_all([a1, a2])
            db.flush()

            # Cross-workspace actor_session is blocked by composite FK.
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    ActorSession(
                        visitor_context_id=vc1.visitor_context_id,
                        actor_id=a2.actor_id,
                        session_token_hash=hashlib.sha256(b"tok-cross").digest(),
                        created_at=now,
                        expires_at=now + timedelta(hours=1),
                    )
                )
                db.flush()

            # Invalid role is blocked.
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    WorkspaceActor(
                        visitor_context_id=vc1.visitor_context_id,
                        actor_ref="admin-1",
                        display_name="Admin",
                        role="admin",
                        access_code_hash=None,
                        created_at=now,
                    )
                )
                db.flush()

            # Duplicate access_code_hash is blocked.
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    WorkspaceActor(
                        visitor_context_id=vc2.visitor_context_id,
                        actor_ref="ops-engineer-1",
                        display_name="Maya Lin",
                        role="engineer",
                        access_code_hash=hashlib.sha256(b"code-1").digest(),
                        created_at=now,
                    )
                )
                db.flush()
        transaction.rollback()


def test_lead_blocked_before_reconcile_mutation(auth_context):
    eng_client, connection, clock, app = auth_context
    boot = bootstrap_workspace(eng_client).json()
    ws_id = boot["visitor_context_id"]
    lead_code = next(c["access_code"] for c in boot["actor_credentials"] if c["role"] == "lead")
    incident_id = eng_client.get(INCIDENT_URL).json()["incident"]["incident_id"]
    inv = eng_client.post(
        "/api/v1/investigations", json={"incident_id": incident_id}, headers=HEADERS
    ).json()
    ev = eng_client.post(
        f"/api/v1/investigations/{inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/evidence-requests",
        json={"state_id": inv["state_id"], "expected_draft_version": inv["draft_version"]},
        headers=HEADERS,
    ).json()

    with TestClient(app, base_url="https://localhost:3000") as lead_client:
        assert login_actor(lead_client, ws_id, "payments-lead-1", lead_code).status_code == 200
        resp = lead_client.post(
            f"/api/v1/investigations/{inv['investigation_id']}/threads/payment_failures/cases/case-failure-001/finding-generations",
            json={
                "state_id": inv["state_id"],
                "expected_draft_version": ev["draft_version"],
                "evidence_request_id": ev["evidence_request_id"],
            },
            headers=HEADERS,
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ROLE_FORBIDDEN"

    with Session(bind=connection) as db:
        gens = db.scalars(
            select(AIGenerationRequest).where(AIGenerationRequest.state_id == UUID(inv["state_id"]))
        ).all()
        assert gens == []
