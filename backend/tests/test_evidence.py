# ruff: noqa: F811 -- pytest injects the imported shared fixture.
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_investigations import HEADERS, bootstrap, create
from test_investigations import context as evidence_context  # noqa: F401

from app import evidence
from app.evidence_schemas import RetrievalCriteria
from app.main import create_app
from app.models import (
    EvidenceRecord,
    EvidenceRequest,
    InvestigationState,
    RequestSource,
    RetrievalResult,
    RetrievalResultRecord,
    StateSource,
    WorkingDraft,
)


def path(workspace, thread="payment_failures", case="case-failure-001"):
    return (
        f"/api/v1/investigations/{workspace['investigation_id']}/threads/{thread}"
        f"/cases/{case}/evidence-requests"
    )


def retrieve(client, workspace, thread="payment_failures", case="case-failure-001", **overrides):
    return client.post(
        path(workspace, thread, case),
        headers=HEADERS,
        json={
            "state_id": workspace["state_id"],
            "expected_draft_version": workspace["draft_version"],
        }
        | overrides,
    )


def refresh(client, workspace):
    return client.get(f"/api/v1/investigations/{workspace['investigation_id']}/workspace").json()


def history(connection, workspace):
    with Session(bind=connection) as db:
        return db.scalars(
            select(EvidenceRequest)
            .where(EvidenceRequest.state_id == UUID(workspace["state_id"]))
            .order_by(EvidenceRequest.requested_at, EvidenceRequest.request_id)
        ).all()


def sources(body):
    return {s["source_key"]: s for g in body["groups"] for s in g["sources"]}


@pytest.mark.parametrize(
    "thread,case,counts",
    [
        ("payment_failures", "case-failure-001", [1, 1, 2, 1]),
        ("possible_duplicates", "case-duplicate-001", [2, 1, 0, 3]),
    ],
)
def test_complete_response_and_durable_membership(evidence_context, thread, case, counts):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    response = retrieve(client, workspace, thread, case)
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["request_id"] != body["evidence_request_id"]
    assert body["status"] == "completed" and body["draft_version"] == 2
    assert response.headers["cache-control"] == "no-store"
    assert [
        sum(s["returned_count"] for s in group["sources"]) for group in body["groups"]
    ] == counts
    outcomes = sources(body)
    assert set(outcomes) == set(evidence.QUERY_SOURCES)
    assert outcomes["stripe"]["completeness"] == "unverified"
    records = [r for s in outcomes.values() for r in s["records"]]
    ids = {r["evidence_record_id"] for r in records}
    assert len(ids) == sum(counts)
    with Session(bind=connection) as db:
        operation = db.get(
            EvidenceRequest, (UUID(workspace["state_id"]), UUID(body["evidence_request_id"]))
        )
        assert operation.status == "completed" and operation.finished_at >= operation.requested_at
        assert operation.deadline_at - operation.requested_at == timedelta(seconds=10)
        assert operation.expected_draft_version == 0
        assert operation.criteria["case_id"] == case
        for model, expected in [
            (RequestSource, 6),
            (RetrievalResult, 6),
            (RetrievalResultRecord, sum(counts)),
        ]:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(
                        model.state_id == operation.state_id,
                        model.request_id == operation.request_id,
                    )
                )
                == expected
            )
        for record in records:
            original = db.get(EvidenceRecord, (operation.state_id, record["evidence_record_id"]))
            assert record["payload"] == original.payload
            assert record["timestamps"] == original.timestamps
            assert record["fixture_provenance"] == original.fixture_provenance
            assert record["source_name"] == original.source_name
            assert "source_digest" not in record
    for link in body["relationships"]:
        assert {link["from_record_id"], link["to_record_id"]} <= ids
        assert link["basis"]["explanation"]
        assert link["basis"]["basis_record_id"] is None or link["basis"]["basis_record_id"] in ids
    if thread == "possible_duplicates":
        assert outcomes["loki"]["match_status"] == outcomes["tempo"]["match_status"] == "no_matches"
        assert outcomes["loki"]["returned_count"] == outcomes["tempo"]["returned_count"] == 0
        attempts = outcomes["internal_payments"]["records"]
        assert all(r["case_association"]["category"] == "documented_lookup" for r in attempts)
        assert all(
            r["case_association"]["basis_record_id"] == "SYN-ZD-HANDOFF-001" for r in attempts
        )
    else:
        ticket = outcomes["zendesk"]["records"][0]
        assert ticket["timestamps"][0]["precision"] == "minute"


@pytest.mark.parametrize("key", ["loki", "stripe"])
def test_partial_failure_retry_preserves_previous_outcome(evidence_context, monkeypatch, key):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    original = evidence.read_source

    def fail(request, criteria, source, *args):
        if source == key:
            raise RuntimeError("private failure details")
        return original(request, criteria, source, *args)

    monkeypatch.setattr(evidence, "read_source", fail)
    first = retrieve(client, workspace)
    assert first.status_code == 200 and first.json()["status"] == "partial"
    outcome = sources(first.json())[key]
    assert outcome["execution_status"] == "failed" and outcome["returned_count"] is None
    assert outcome["records"] == [] and "private" not in first.text
    old_id = first.json()["evidence_request_id"]
    monkeypatch.setattr(evidence, "read_source", original)
    second = retrieve(client, refresh(client, workspace), retry_of_request_id=old_id)
    assert second.status_code == 200 and second.json()["status"] == "completed"
    assert second.json()["evidence_request_id"] != old_id
    rows = history(connection, workspace)
    assert len(rows) == 2 and {r.status for r in rows} == {"partial", "completed"}
    assert next(r for r in rows if r.status == "completed").retry_of_request_id == UUID(old_id)
    with Session(bind=connection) as db:
        old = db.get(RetrievalResult, (UUID(workspace["state_id"]), UUID(old_id), key))
        assert old.execution_status == "failed" and old.returned_count is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(EvidenceRecord)
                .where(EvidenceRecord.state_id == UUID(workspace["state_id"]))
            )
            == 14
        )


def test_all_source_failures_are_persisted_not_empty_success(evidence_context, monkeypatch):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()

    def fail(*args):
        raise RuntimeError("private")

    monkeypatch.setattr(evidence, "read_source", fail)
    result = retrieve(client, workspace)
    assert (
        result.status_code == 503 and result.json()["error"]["code"] == "EVIDENCE_RETRIEVAL_FAILED"
    )
    assert result.json()["error"]["details"]["draft_version"] == 2
    assert history(connection, workspace)[0].status == "failed"
    with Session(bind=connection) as db:
        rows = db.scalars(
            select(RetrievalResult).where(RetrievalResult.state_id == UUID(workspace["state_id"]))
        ).all()
        assert len(rows) == 6 and all(
            r.returned_count is None and r.execution_status == "failed" for r in rows
        )


def test_failed_postgresql_source_rolls_back_before_following_sources(
    evidence_context, monkeypatch
):
    client, _, _, _, _ = evidence_context
    workspace = create(client).json()
    original = evidence.read_source

    def fail(request, criteria, key, *args):
        if key == "stripe":
            with evidence.Session(request.app.state.engine) as db, db.begin():
                db.execute(text("SELECT 1 / 0"))
        return original(request, criteria, key, *args)

    monkeypatch.setattr(evidence, "read_source", fail)
    result = retrieve(client, workspace)
    assert result.status_code == 200 and result.json()["status"] == "partial"
    outcomes = sources(result.json())
    assert outcomes["stripe"]["execution_status"] == "failed"
    assert all(
        outcomes[k]["execution_status"] == "completed"
        for k in evidence.QUERY_SOURCES
        if k != "stripe"
    )


@pytest.mark.parametrize("availability", ["not_included", "not_constructed", "unavailable"])
def test_declared_source_gap_is_not_query_failure(evidence_context, availability):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        source = db.get(StateSource, (UUID(workspace["state_id"]), "stripe"))
        source.availability = availability
        source.limitations = ["Test-only coverage gap"]
    result = retrieve(client, workspace)
    assert result.status_code == 200
    gap = sources(result.json())["stripe"]
    assert gap["execution_status"] == "completed" and gap["availability"] == availability
    assert (
        gap["match_status"] == "not_evaluated"
        and gap["returned_count"] is None
        and gap["records"] == []
    )
    assert gap["limitations"] == ["Test-only coverage gap"]


@pytest.mark.parametrize(
    "overrides,status,code",
    [
        ({"state_id": str(uuid4())}, 409, "STALE_STATE"),
        ({"expected_draft_version": 1}, 409, "STALE_DRAFT_VERSION"),
        ({"expected_draft_version": -1}, 422, "VALIDATION_ERROR"),
        ({"expected_draft_version": True}, 422, "VALIDATION_ERROR"),
        ({"expected_draft_version": "0"}, 422, "VALIDATION_ERROR"),
        ({"criteria": {"sql": "SELECT * FROM evidence_records"}}, 422, "VALIDATION_ERROR"),
        ({"limit": 999999}, 422, "VALIDATION_ERROR"),
        ({"source_keys": ["stripe"]}, 422, "VALIDATION_ERROR"),
        ({"retry_of_request_id": str(uuid4())}, 409, "INVALID_RETRY_REFERENCE"),
    ],
)
def test_invalid_requests_create_no_history(evidence_context, overrides, status, code):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    result = retrieve(client, workspace, **overrides)
    assert result.status_code == status and result.json()["error"]["code"] == code
    assert history(connection, workspace) == []


def test_auth_thread_case_and_cross_visitor_boundaries(evidence_context):
    client, connection, app, clock, _ = evidence_context
    workspace = create(client).json()
    for thread, case, status in [
        ("payment_failures", "case-duplicate-001", 404),
        ("possible_duplicates", "case-failure-001", 404),
        ("payment_failures", "missing", 404),
        ("invalid", "case-failure-001", 422),
    ]:
        assert retrieve(client, workspace, thread, case).status_code == status
    with TestClient(app, base_url="https://localhost:3000") as other:
        assert retrieve(other, workspace).json()["error"]["code"] == "SESSION_REQUIRED"
        other.cookies.set("__Host-opspilot_visitor", "x" * 43, domain="localhost.local", path="/")
        assert retrieve(other, workspace).json()["error"]["code"] == "SESSION_INVALID"
        other.cookies.clear()
        bootstrap(other)
        owned = create(other).json()
        assert retrieve(other, workspace).status_code == 404
        assert retrieve(client, workspace, state_id=owned["state_id"]).status_code == 409
        assert retrieve(other, owned).status_code == 200
    clock.now += timedelta(hours=24)
    assert retrieve(client, workspace).json()["error"]["code"] == "SESSION_EXPIRED"
    assert history(connection, workspace) == []


def test_origin_body_and_query_guards(evidence_context):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    target = path(workspace)
    payload = {"state_id": workspace["state_id"], "expected_draft_version": 0}
    assert client.post(target, json=payload).status_code == 403
    assert client.post(target, headers=HEADERS, content="{}").status_code == 415
    assert client.post(target, headers=HEADERS, json={"huge": "x" * 4096}).status_code == 413
    assert client.post(target + "?sql=select", headers=HEADERS, json=payload).status_code == 422
    assert history(connection, workspace) == []


def test_bounded_criteria_and_completeness_reject_truncated_results(evidence_context, monkeypatch):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    with pytest.raises(ValueError):
        RetrievalCriteria(
            state_id=uuid4(),
            thread_kind="payment_failures",
            case_id="case-failure-001",
            source_keys=evidence.QUERY_SOURCES,
            record_ids=["a"] * 15,
            max_records=15,
        )

    # Query retains the linked inventory even if an allowlisted membership is missing.
    def truncate(connection, cursor, statement, parameters, context, executemany):
        if (
            statement.startswith("SELECT evidence_records.")
            and "JOIN case_evidence_links" in statement
        ):
            return statement + " OFFSET 100", parameters
        return statement, parameters

    event.listen(connection, "before_cursor_execute", truncate, retval=True)
    try:
        result = retrieve(client, workspace)
    finally:
        event.remove(connection, "before_cursor_execute", truncate)
    assert result.status_code == 200  # Valid zero-match sources remain completed.
    outcomes = sources(result.json())
    assert outcomes["internal_payments"]["execution_status"] == "failed"
    assert outcomes["support_lookup"]["match_status"] == "no_matches"


def start_only(client, workspace, monkeypatch):
    class Crash(Exception):
        pass

    def crash(*args):
        raise Crash()

    with monkeypatch.context() as patch:
        patch.setattr(evidence, "collect", crash)
        assert retrieve(client, workspace).status_code == 500


@pytest.mark.parametrize("entrypoint", ["workspace", "cases", "retry"])
def test_crash_recovery_is_independently_committed_before_version_rejection(
    evidence_context, monkeypatch, entrypoint
):
    client, connection, _, clock, _ = evidence_context
    workspace = create(client).json()
    start_only(client, workspace, monkeypatch)
    old = history(connection, workspace)[0]
    assert old.status == "pending"
    assert (
        retrieve(client, workspace | {"draft_version": 1}).json()["error"]["code"]
        == "OPERATION_IN_PROGRESS"
    )
    clock.now += timedelta(seconds=11)
    if entrypoint == "workspace":
        assert refresh(client, workspace)["draft_version"] == 2
    elif entrypoint == "cases":
        response = client.get(
            path(workspace).split("/case-failure-001/")[0],
            params={"state_id": workspace["state_id"]},
        )
        assert response.status_code == 200 and response.json()["draft_version"] == 2
    else:
        response = retrieve(client, workspace, retry_of_request_id=str(old.request_id))
        assert (
            response.status_code == 409
            and response.json()["error"]["details"]["draft_version"] == 2
        )
    assert (
        len(history(connection, workspace)) == 1
        and history(connection, workspace)[0].status == "interrupted"
    )
    result = retrieve(client, refresh(client, workspace), retry_of_request_id=str(old.request_id))
    assert result.status_code == 200 and result.json()["draft_version"] == 4


def test_finalization_failure_rolls_back_results_and_keeps_committed_start(
    evidence_context, monkeypatch
):
    client, connection, _, clock, _ = evidence_context
    workspace = create(client).json()
    original = evidence.persist_outcomes

    def fail(*args):
        original(*args)
        raise IntegrityError("injected", {}, Exception())

    monkeypatch.setattr(evidence, "persist_outcomes", fail)
    result = retrieve(client, workspace)
    assert result.status_code == 503
    assert history(connection, workspace)[0].status == "pending"
    with Session(bind=connection) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(RetrievalResultRecord)
                .where(RetrievalResultRecord.state_id == UUID(workspace["state_id"]))
            )
            == 0
        )
        rows = db.scalars(
            select(RetrievalResult).where(RetrievalResult.state_id == UUID(workspace["state_id"]))
        ).all()
        assert len(rows) == 6 and all(r.execution_status == "pending" for r in rows)
    clock.now += timedelta(seconds=11)
    assert refresh(client, workspace)["draft_version"] == 2


def test_failed_start_has_no_history_or_version_change(evidence_context, monkeypatch):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()

    def fail(draft, clock):
        raise IntegrityError("injected", {}, Exception())

    monkeypatch.setattr(evidence, "advance", fail)
    assert retrieve(client, workspace).status_code == 503
    assert history(connection, workspace) == []
    assert refresh(client, workspace)["draft_version"] == 0


@pytest.mark.parametrize("change", ["version", "state", "expiry"])
def test_late_results_cannot_attach_after_context_changes(evidence_context, monkeypatch, change):
    client, connection, _, clock, _ = evidence_context
    workspace = create(client).json()
    original = evidence.collect

    def changed(*args):
        outcomes = original(*args)
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
            draft = db.get(WorkingDraft, UUID(workspace["investigation_id"]))
            if change == "version":
                draft.draft_version += 1
            elif change == "state":
                old = db.get(InvestigationState, draft.state_id)
                new = InvestigationState(
                    investigation_id=old.investigation_id,
                    dataset_version_id=old.dataset_version_id,
                    incident_context=old.incident_context,
                    limitations=old.limitations,
                )
                db.add(new)
                db.flush()
                draft.state_id = new.state_id
            else:
                clock.now += timedelta(hours=24)
        return outcomes

    monkeypatch.setattr(evidence, "collect", changed)
    result = retrieve(client, workspace)
    assert result.status_code == (401 if change == "expiry" else 409)
    assert history(connection, workspace)[0].status == (
        "stale" if change == "version" else "pending"
    )
    with Session(bind=connection) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(RetrievalResultRecord)
                .where(RetrievalResultRecord.state_id == UUID(workspace["state_id"]))
            )
            == 0
        )


def test_deadline_is_interrupted_with_unknown_counts(evidence_context, monkeypatch):
    client, connection, _, clock, _ = evidence_context
    workspace = create(client).json()
    original = evidence.collect

    def late(*args):
        outcomes = original(*args)
        clock.now += timedelta(seconds=11)
        return outcomes

    monkeypatch.setattr(evidence, "collect", late)
    assert retrieve(client, workspace).status_code == 503
    assert history(connection, workspace)[0].status == "interrupted"
    with Session(bind=connection) as db:
        assert all(
            r.execution_status == "interrupted" and r.returned_count is None
            for r in db.scalars(
                select(RetrievalResult).where(
                    RetrievalResult.state_id == UUID(workspace["state_id"])
                )
            )
        )


def test_monotonic_budget_does_not_start_reads_without_connection_reserve(
    evidence_context, monkeypatch
):
    client, _, _, _, _ = evidence_context
    workspace = create(client).json()
    original = evidence.collect

    def elapsed(request, criteria, sources, inventory, end):
        return original(request, criteria, sources, inventory, evidence.monotonic() + 1)

    monkeypatch.setattr(evidence, "collect", elapsed)
    result = retrieve(client, workspace)
    assert result.status_code == 503


@pytest.mark.parametrize("mutation", ["thread", "source", "record", "retry", "finish", "count"])
def test_history_database_constraints(evidence_context, mutation):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    response = retrieve(client, workspace).json()
    state, operation = UUID(workspace["state_id"]), UUID(response["evidence_request_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            if mutation == "thread":
                db.get(EvidenceRequest, (state, operation)).thread_kind = "possible_duplicates"
            elif mutation == "source":
                db.add(RequestSource(state_id=state, request_id=operation, source_key="missing"))
            elif mutation == "record":
                db.add(
                    RetrievalResultRecord(
                        state_id=state,
                        request_id=operation,
                        source_key="stripe",
                        evidence_record_id="SYN-ZD-TICKET-001",
                        match_basis={},
                    )
                )
            elif mutation == "retry":
                db.get(EvidenceRequest, (state, operation)).retry_of_request_id = operation
            elif mutation == "finish":
                db.get(EvidenceRequest, (state, operation)).finished_at = None
            else:
                db.get(RetrievalResult, (state, operation, "stripe")).returned_count = None
            db.flush()
    for model in (EvidenceRequest, RequestSource, RetrievalResult, RetrievalResultRecord):
        assert all(
            "state_id" in fk["constrained_columns"]
            for fk in inspect(connection).get_foreign_keys(model.__tablename__)
        )


def test_successful_reinspection_creates_history_but_cannot_be_retry_target(evidence_context):
    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    first = retrieve(client, workspace).json()
    current = refresh(client, workspace)
    assert (
        retrieve(client, current, retry_of_request_id=first["evidence_request_id"]).status_code
        == 409
    )
    assert retrieve(client, current).status_code == 200
    assert len(history(connection, workspace)) == 2


def test_history_and_evidence_survive_new_application_and_engine(database):
    engine, settings = database
    with TestClient(create_app(settings), base_url="https://localhost:3000") as client:
        bootstrap(client)
        workspace = create(client).json()
        first = retrieve(client, workspace).json()
        jar = client.cookies
    with TestClient(create_app(settings), base_url="https://localhost:3000") as restarted:
        restarted.cookies.update(jar)
        current = refresh(restarted, workspace)
        assert current["draft_version"] == first["draft_version"]
        second = retrieve(restarted, current).json()
        assert (
            second["groups"] == first["groups"]
            and second["relationships"] == first["relationships"]
        )
        assert second["evidence_request_id"] != first["evidence_request_id"]
    with engine.connect() as connection:
        assert len(history(connection, workspace)) == 2


def test_concurrent_request_start_is_serialized_across_connections(database, monkeypatch):
    _, settings = database
    entered, release = Event(), Event()
    original = evidence.collect

    def paused(*args):
        entered.set()
        assert release.wait(8)
        return original(*args)

    monkeypatch.setattr(evidence, "collect", paused)
    with (
        TestClient(create_app(settings), base_url="https://localhost:3000") as first,
        TestClient(create_app(settings), base_url="https://localhost:3000") as second,
    ):
        bootstrap(first)
        workspace = create(first).json()
        second.cookies.update(first.cookies)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(retrieve, first, workspace)
            assert entered.wait(8)
            try:
                result = retrieve(second, workspace | {"draft_version": 1})
                assert (
                    result.status_code == 409
                    and result.json()["error"]["code"] == "OPERATION_IN_PROGRESS"
                )
            finally:
                release.set()
            assert future.result(timeout=15).status_code == 200


def test_session_expiry_before_start_commit_leaves_no_request(evidence_context, monkeypatch):
    client, connection, _, clock, _ = evidence_context
    workspace = create(client).json()
    original = evidence.advance

    def expire(draft, active_clock):
        original(draft, active_clock)
        clock.now += timedelta(hours=24)

    monkeypatch.setattr(evidence, "advance", expire)
    assert retrieve(client, workspace).status_code == 401
    assert history(connection, workspace) == []
    with Session(bind=connection) as db:
        assert db.get(WorkingDraft, UUID(workspace["investigation_id"])).draft_version == 0


def test_retry_cannot_reference_another_case_or_visitor(evidence_context, monkeypatch):
    client, _, app, _, _ = evidence_context
    workspace = create(client).json()
    original = evidence.read_source

    def fail(*args):
        raise RuntimeError("test failure")

    monkeypatch.setattr(evidence, "read_source", fail)
    first = retrieve(client, workspace).json()["error"]["details"]["evidence_request_id"]
    monkeypatch.setattr(evidence, "read_source", original)
    current = refresh(client, workspace)
    assert (
        retrieve(
            client, current, "possible_duplicates", "case-duplicate-001", retry_of_request_id=first
        ).json()["error"]["code"]
        == "INVALID_RETRY_REFERENCE"
    )
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        owned = create(other).json()
        assert (
            retrieve(other, owned, retry_of_request_id=first).json()["error"]["code"]
            == "INVALID_RETRY_REFERENCE"
        )


def test_real_slow_source_is_bounded_by_postgresql_timeout(evidence_context):
    from time import monotonic

    client, connection, _, _, _ = evidence_context
    workspace = create(client).json()
    slowed = False

    def slow(connection, cursor, statement, parameters, context, executemany):
        nonlocal slowed
        if (
            not slowed
            and statement.startswith("SELECT evidence_records.")
            and "JOIN case_evidence_links" in statement
        ):
            slowed = True
            # The service's SET LOCAL statement_timeout cancels this real blocked I/O.
            return "SELECT pg_sleep(4)", {}
        return statement, parameters

    event.listen(connection, "before_cursor_execute", slow, retval=True)
    started = monotonic()
    try:
        result = retrieve(client, workspace)
    finally:
        event.remove(connection, "before_cursor_execute", slow)
    assert monotonic() - started < 5
    assert result.status_code == 200 and result.json()["status"] == "partial"
    assert sources(result.json())["internal_payments"]["execution_status"] == "failed"


def test_history_and_evidence_survive_real_https_process_restart(database):
    import os
    import socket
    import ssl
    import subprocess
    import sys
    from pathlib import Path
    from time import monotonic, sleep

    import httpx

    _, settings = database
    root = Path(__file__).resolve().parents[2]
    cert = root / ".certs" / "localhost.pem"
    key = root / ".certs" / "localhost-key.pem"
    assert cert.is_file() and key.is_file(), "Local HTTPS test certificates are required"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = os.environ | {"DATABASE_URL": settings.database_url.get_secret_value()}
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
        "--log-level",
        "critical",
        "--ssl-certfile",
        str(cert),
        "--ssl-keyfile",
        str(key),
    ]
    base = f"https://localhost:{port}"
    tls = ssl.create_default_context(cafile=str(cert))

    def launch():
        process = subprocess.Popen(
            args,
            cwd=root / "backend",
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = monotonic() + 8
        while monotonic() < deadline:
            try:
                with httpx.Client(base_url=base, verify=tls, trust_env=False) as probe:
                    if probe.get("/api/v1/health").status_code == 200:
                        return process
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                break
            sleep(0.05)
        process.terminate()
        process.wait(timeout=5)
        pytest.fail("Temporary HTTPS backend did not become ready")

    def stop(process):
        process.terminate()
        process.wait(timeout=5)

    process = launch()
    try:
        with httpx.Client(base_url=base, verify=tls, trust_env=False) as client:
            bootstrap(client)
            workspace = create(client).json()
            first = retrieve(client, workspace)
            assert first.status_code == 200
            jar = client.cookies
    finally:
        stop(process)
    process = launch()
    try:
        # A fresh client/pool proves no previous HTTP connection or in-memory app survives.
        with httpx.Client(base_url=base, verify=tls, trust_env=False) as client:
            client.cookies.update(jar)
            current = refresh(client, workspace)
            assert current["state_id"] == workspace["state_id"]
            assert current["draft_version"] == first.json()["draft_version"]
            second = retrieve(client, current)
            assert second.status_code == 200 and second.json()["groups"] == first.json()["groups"]
            assert second.json()["evidence_request_id"] != first.json()["evidence_request_id"]
    finally:
        stop(process)


@pytest.mark.parametrize("reference", ["record", "request", "retry"])
def test_same_state_history_fks_reject_foreign_only_references(evidence_context, reference):
    client, connection, app, _, _ = evidence_context
    first = create(client).json()
    own_response = retrieve(client, first).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        second = create(other).json()
        foreign_response = retrieve(other, second).json()
    state, foreign = UUID(first["state_id"]), UUID(second["state_id"])
    request_id = UUID(own_response["evidence_request_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        original = db.get(EvidenceRecord, (foreign, "SYN-STRIPE-FAIL-001"))
        values = {
            column.name: getattr(original, column.name)
            for column in EvidenceRecord.__table__.columns
        }
        values["evidence_record_id"] = "foreign-only"
        db.add(EvidenceRecord(**values))
        db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            if reference == "record":
                db.add(
                    RetrievalResultRecord(
                        state_id=state,
                        request_id=request_id,
                        source_key="stripe",
                        evidence_record_id="foreign-only",
                        match_basis={},
                    )
                )
            elif reference == "request":
                db.add(
                    RequestSource(
                        state_id=state,
                        request_id=UUID(foreign_response["evidence_request_id"]),
                        source_key="stripe",
                    )
                )
            else:
                db.get(EvidenceRequest, (state, request_id)).retry_of_request_id = UUID(
                    foreign_response["evidence_request_id"]
                )
            db.flush()


def test_duplicate_zendesk_records_are_oldest_first(evidence_context):
    client, _, _, _, _ = evidence_context
    workspace = create(client).json()
    response = retrieve(client, workspace, "possible_duplicates", "case-duplicate-001")
    assert response.status_code == 200
    zendesk = sources(response.json())["zendesk"]["records"]
    assert [r["evidence_record_id"] for r in zendesk] == [
        "SYN-ZD-TICKET-002",
        "SYN-ZD-ESCALATION-001",
    ]
    assert zendesk[0]["timestamps"][0]["utc_lower"] == "2026-10-20T02:33:00Z"
    assert zendesk[1]["timestamps"][0]["utc_lower"] == "2026-10-20T02:40:00Z"
    assert all(r["timestamps"][0]["precision"] == "minute" for r in zendesk)


def test_source_chronology_uses_timezone_bounds_and_preserves_missing_precision():
    from copy import deepcopy

    from app.evidence_schemas import EvidenceRecordView

    def record(key, lower=None, zone=None, precision="unknown", upper=None):
        return EvidenceRecordView(
            evidence_record_id=key,
            source_key="zendesk",
            source_name="Zendesk",
            record_type="ticket",
            source_record_reference=None,
            fixture_provenance={
                "version_label": "test",
                "fixture_record_id": key,
                "origin": "synthetic test",
            },
            timestamps=[
                {
                    "role": "Created",
                    "raw": lower,
                    "timezone": zone,
                    "precision": precision,
                    "utc_lower": lower,
                    "utc_upper": upper or lower,
                    "missing_reason": "Not supplied" if lower is None else None,
                }
            ],
            payload={},
            case_association={
                "category": "unverified",
                "explanation": "test",
                "matched_fields": {},
                "basis_record_id": None,
            },
        )

    earlier = record("z-earlier", "2026-10-20T10:30:00+08:00", "Asia/Singapore", "minute")
    later = record("a-later", "2026-10-20T02:31:01Z", "UTC", "second")
    tied = record("b-same-minute", "2026-10-20T02:30:00Z", "UTC", "minute")
    ranged = record(
        "range",
        "2026-10-20T07:59:00+05:30",
        "Asia/Kolkata",
        "minute_range",
        "2026-10-20T08:01:00+05:30",
    )
    unknown = record("missing")
    unknown_zone = record("unknown-zone", "2026-10-20T01:00:00Z", None, "minute")
    unknown_precision = record("unknown-precision", "2026-10-20T01:00:00Z", "UTC", "unknown")
    records = [unknown_zone, later, unknown, earlier, ranged, unknown_precision, tied]
    before = deepcopy([r.model_dump() for r in records])
    assert [r.evidence_record_id for r in sorted(records, key=evidence.record_chronology)] == [
        "range",
        "b-same-minute",
        "z-earlier",
        "a-later",
        "missing",
        "unknown-precision",
        "unknown-zone",
    ]
    # Sorting does not populate missing times, replace precision, or rewrite original source text.
    assert [r.model_dump() for r in records] == before
    assert earlier.timestamps[0].raw == "2026-10-20T10:30:00+08:00"
    assert earlier.timestamps[0].precision == "minute"
    assert unknown.timestamps[0].utc_lower is None
