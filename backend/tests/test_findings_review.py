# ruff: noqa: F811 -- pytest injects imported shared fixtures.
"""Regressions for the three Task 5A merge blockers; no live provider calls."""

import asyncio
from datetime import timedelta
from math import inf, nan, nextafter
from threading import Event, get_ident, local

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_evidence import refresh
from test_findings import attempts, endpoint, generate, graph_counts, prepare
from test_findings import enabled as enabled
from test_investigations import HEADERS, context  # noqa: F401

from app import findings
from app.config import (
    FINDINGS_DEADLINE_CONFIGURATION_ERROR,
    FINDINGS_PUBLICATION_RESERVE_SECONDS,
    Settings,
)
from app.main import create_app
from app.models import AIGenerationRequest


@pytest.mark.parametrize("stage", ["publish", "flush", "view", "authorization"])
@pytest.mark.parametrize("expired_clock", ["utc", "monotonic"])
def test_deadline_during_publication_rolls_back_graph_and_keeps_success_slot(
    enabled, monkeypatch, stage, expired_clock
):
    client, connection, _, clock, _ = enabled
    workspace = prepare(client)
    expired, offset = False, 0
    real_monotonic = findings.monotonic
    monkeypatch.setattr(findings, "monotonic", lambda: real_monotonic() + offset)

    def expire():
        nonlocal expired, offset
        if not expired:
            expired = True
            if expired_clock == "utc":
                clock.now += timedelta(seconds=21)
            else:
                offset = 21

    if stage in {"publish", "view"}:
        original = getattr(findings, stage)

        def after_phase(*args, **kwargs):
            result = original(*args, **kwargs)
            expire()
            return result

        monkeypatch.setattr(findings, stage, after_phase)
    elif stage == "flush":

        def after_flush(db, flush_context):
            if any(
                isinstance(row, AIGenerationRequest) and row.status == "completed"
                for row in db.identity_map.values()
            ):
                expire()

        event.listen(Session, "after_flush", after_flush)
    else:
        original = findings.authenticate

        def after_authorization(db, *args):
            actor = original(db, *args)
            if any(
                isinstance(row, AIGenerationRequest) and row.status == "completed"
                for row in db.identity_map.values()
            ):
                expire()
            return actor

        monkeypatch.setattr(findings, "authenticate", after_authorization)
    try:
        response = generate(client, workspace)
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "AI_DEADLINE_EXCEEDED"
        assert expired
        assert graph_counts(connection, workspace) == [0] * 5
        history = attempts(connection, workspace)
        assert len(history) == 1 and history[0].status == "interrupted"
        assert history[0].normalized_output is None and history[0].retryable
        workspace["draft_version"] = refresh(client, workspace)["draft_version"]
        assert workspace["draft_version"] == 4
        retry = generate(client, workspace, retry_of_generation_id=str(history[0].generation_id))
        assert retry.status_code == 201, retry.text
        assert [row.status for row in attempts(connection, workspace)] == [
            "interrupted",
            "completed",
        ]
        assert graph_counts(connection, workspace)[:3] == [2, 2, 2]
    finally:
        if stage == "flush":
            event.remove(Session, "after_flush", after_flush)


@pytest.mark.parametrize("phase", ["start", "reserve", "finalize"])
def test_database_phase_wait_does_not_block_unrelated_request_on_same_event_loop(
    enabled, monkeypatch, phase
):
    client, connection, app, _, _ = enabled
    workspace = prepare(client)
    entered, release = Event(), Event()
    active = local()
    waiting_threads = []
    original = getattr(findings, phase)

    def phase_with_wait(*args, **kwargs):
        active.target_phase = True
        try:
            return original(*args, **kwargs)
        finally:
            active.target_phase = False

    def database_wait(conn, cursor, statement, parameters, context, executemany):
        if getattr(active, "target_phase", False) and not entered.is_set():
            waiting_threads.append(get_ident())
            entered.set()
            # A bounded simulated driver wait within the phase's own database session.
            assert release.wait(5), "Unrelated request could not release the database phase"

    monkeypatch.setattr(findings, phase, phase_with_wait)
    event.listen(connection, "before_cursor_execute", database_wait)

    async def same_loop_requests():
        loop_thread = get_ident()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://localhost:3000", cookies=client.cookies
        ) as browser:
            generation = asyncio.create_task(
                browser.post(
                    endpoint(workspace),
                    headers=HEADERS,
                    json={
                        "state_id": workspace["state_id"],
                        "expected_draft_version": workspace["draft_version"],
                        "evidence_request_id": workspace["evidence_request_id"],
                    },
                )
            )
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                health = await asyncio.wait_for(browser.get("/api/v1/health"), timeout=2)
                assert health.status_code == 200
                assert not generation.done() and not release.is_set()
                assert len(waiting_threads) == 1
                assert waiting_threads[0] != loop_thread
            finally:
                release.set()
                response = await asyncio.wait_for(generation, timeout=10)
            assert response.status_code == 201, response.text

    try:
        asyncio.run(same_loop_requests())
    finally:
        release.set()
        event.remove(connection, "before_cursor_execute", database_wait)


def test_failed_interruption_recording_keeps_rolled_back_graph_recoverable(enabled, monkeypatch):
    client, connection, _, clock, _ = enabled
    workspace = prepare(client)
    original = findings.publish

    def expire_after_publish(*args):
        original(*args)
        clock.now += timedelta(seconds=21)

    def fail_interruption_flush(db, flush_context):
        if any(
            isinstance(row, AIGenerationRequest) and row.status == "interrupted"
            for row in db.identity_map.values()
        ):
            raise IntegrityError("injected interruption write failure", {}, Exception())

    monkeypatch.setattr(findings, "publish", expire_after_publish)
    event.listen(Session, "after_flush", fail_interruption_flush)
    try:
        response = generate(client, workspace)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        event.remove(Session, "after_flush", fail_interruption_flush)
    assert graph_counts(connection, workspace) == [0] * 5
    assert attempts(connection, workspace)[0].status == "pending"
    refresh(client, workspace)
    assert attempts(connection, workspace)[0].status == "interrupted"


INVALID_DEADLINES = [
    0,
    FINDINGS_PUBLICATION_RESERVE_SECONDS - 0.001,
    FINDINGS_PUBLICATION_RESERVE_SECONDS,
    inf,
    nan,
]
VALID_DEADLINES = [
    nextafter(FINDINGS_PUBLICATION_RESERVE_SECONDS, inf),
    FINDINGS_PUBLICATION_RESERVE_SECONDS + 0.001,
    20,
]


@pytest.mark.parametrize("deadline", INVALID_DEADLINES)
def test_deadline_configuration_rejects_no_publication_budget(deadline):
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://localhost/unused",
            ai_findings_deadline_seconds=deadline,
        )


@pytest.mark.parametrize("deadline", INVALID_DEADLINES)
def test_application_startup_rechecks_even_unvalidated_settings(deadline, monkeypatch):
    settings = Settings(database_url="postgresql+psycopg://localhost/unused")
    settings = settings.model_copy(update={"ai_findings_deadline_seconds": deadline})

    def unexpected_database_access(*args):
        pytest.fail("Invalid configuration reached database initialization")

    monkeypatch.setattr("app.main.build_engine", unexpected_database_access)
    with pytest.raises(RuntimeError) as error, TestClient(create_app(settings)):
        pass
    assert str(error.value) == FINDINGS_DEADLINE_CONFIGURATION_ERROR


@pytest.mark.parametrize("deadline", VALID_DEADLINES)
def test_valid_deadline_boundary_allows_application_startup(deadline, monkeypatch):
    settings = Settings(
        database_url="postgresql+psycopg://localhost/unused", ai_findings_deadline_seconds=deadline
    )

    class Engine:
        disposed = False

        def dispose(self):
            self.disposed = True

    engine = Engine()
    monkeypatch.setattr("app.main.build_engine", lambda *_: engine)
    monkeypatch.setattr("app.main.initialize_catalog", lambda *_: None)
    app = create_app(settings)
    with TestClient(app):
        assert app.state.settings.ai_findings_deadline_seconds == deadline
    assert engine.disposed


@pytest.mark.parametrize("deadline", ["6", "5.999", "nan", "inf"])
def test_environment_deadline_error_is_explicit_without_exposing_configuration(
    deadline, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:PRIVATE_CONFIG@localhost/unused")
    monkeypatch.setenv("AI_FINDINGS_DEADLINE_SECONDS", deadline)
    with pytest.raises(RuntimeError) as error:
        Settings.from_env()
    assert str(error.value) == FINDINGS_DEADLINE_CONFIGURATION_ERROR
    assert "PRIVATE_CONFIG" not in str(error.value)
