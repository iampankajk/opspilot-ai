from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.catalog import FixtureBundle, initialize_catalog, load_fixture
from app.main import create_app
from app.models import (
    DatasetVersion,
    Investigation,
    InvestigationState,
    StateSource,
    ThreadState,
    WorkingDraft,
)
from app.visitor_sessions import get_clock

HEADERS = {"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"}
INCIDENT = "/api/v1/incidents/INC-2026-1042"


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now


def bootstrap(client):
    response = client.post("/api/v1/visitor-session", json={}, headers=HEADERS)
    assert response.status_code == 201
    return response.json()


def create(client, incident_id=None, **extra):
    if incident_id is None:
        incident_id = client.get(INCIDENT).json()["incident"]["incident_id"]
    return client.post(
        "/api/v1/investigations", json={"incident_id": incident_id} | extra, headers=HEADERS
    )


@pytest.fixture
def context(database, monkeypatch):
    engine, settings = database
    with engine.connect() as connection:
        transaction = connection.begin()

        def scoped_session(*args, **kwargs):
            kwargs.pop("bind", None)
            return Session(bind=connection, join_transaction_mode="create_savepoint", **kwargs)

        monkeypatch.setattr("app.visitor_sessions.Session", scoped_session)
        monkeypatch.setattr("app.investigations.Session", scoped_session)
        monkeypatch.setattr("app.evidence.Session", scoped_session)
        app = create_app(settings)
        clock = Clock()
        app.dependency_overrides[get_clock] = lambda: clock
        with TestClient(app, base_url="https://localhost:3000") as client:
            owner = bootstrap(client)
            yield client, connection, app, clock, owner
        transaction.rollback()


def test_incident_contract_requires_cookie_and_preserves_source_time(context):
    client, _, _, _, _ = context
    response = client.get(INCIDENT)
    assert response.status_code == 200
    entry = response.json()
    assert set(entry) == {"incident", "dataset_version"}
    incident = entry["incident"]
    assert incident["synthetic"] is True
    assert incident["title"] == "Payment failure rate exceeded threshold"
    assert incident["category"] is None and incident["description"] is None
    assert incident["incident_time"]["timezone"] == "Asia/Singapore"
    assert incident["incident_time"]["precision"] == "second"
    assert incident["incident_time"]["utc_lower"] == "2026-10-20T02:30:00Z"
    assert response.headers["cache-control"] == "no-store"
    UUID(response.headers["X-Request-ID"])


def test_create_is_atomic_complete_and_reused_without_version_change(context):
    client, connection, _, _, owner = context
    first = create(client)
    assert first.status_code == 201
    workspace = first.json()
    assert set(workspace) == {
        "investigation_id",
        "state_id",
        "draft_version",
        "dataset_version",
        "incident",
        "threads",
    }
    assert workspace["draft_version"] == 0
    assert workspace["threads"] == [
        {"thread_kind": "payment_failures", "label": "Payment failures", "case_count": 1},
        {"thread_kind": "possible_duplicates", "label": "Possible duplicates", "case_count": 1},
    ]
    with Session(bind=connection) as db:
        investigation = db.get(Investigation, UUID(workspace["investigation_id"]))
        assert str(investigation.visitor_context_id) == owner["visitor_context_id"]
        draft = db.get(WorkingDraft, investigation.investigation_id)
        assert draft.has_unversioned_changes is True
        assert str(draft.state_id) == workspace["state_id"]
        assert (
            db.scalar(
                select(func.count())
                .select_from(ThreadState)
                .where(ThreadState.state_id == draft.state_id)
            )
            == 2
        )
        sources = db.scalars(
            select(StateSource).where(StateSource.state_id == draft.state_id)
        ).all()
        assert len(sources) == 9
        stripe = next(source for source in sources if source.source_key == "stripe")
        assert stripe.completeness == "unverified"
        assert any("bank-posting" in limitation for limitation in stripe.limitations)
    assert create(client).status_code == 200
    assert create(client).json() == workspace
    assert (
        client.get(f"/api/v1/investigations/{workspace['investigation_id']}/workspace").json()
        == workspace
    )


def test_same_incident_two_visitors_have_independent_workspaces_and_safe_404(context):
    client, _, app, _, _ = context
    first = create(client).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        second = create(other).json()
        assert second["incident"]["incident_id"] == first["incident"]["incident_id"]
        assert second["investigation_id"] != first["investigation_id"]
        assert second["state_id"] != first["state_id"]
        foreign = other.get(f"/api/v1/investigations/{first['investigation_id']}/workspace")
        missing = other.get(f"/api/v1/investigations/{uuid4()}/workspace")
        assert foreign.status_code == missing.status_code == 404
        for response in (foreign, missing):
            error = response.json()["error"]
            assert (error["code"], error["message"], error["details"]) == (
                "NOT_FOUND",
                "Resource not found.",
                {},
            )
        assert (
            client.get(f"/api/v1/investigations/{second['investigation_id']}/workspace").status_code
            == 404
        )


def test_missing_incident_does_not_create_investigation(context):
    client, connection, _, _, owner = context
    assert client.get("/api/v1/incidents/INC-MISSING").status_code == 404
    assert create(client, str(uuid4())).status_code == 404
    assert (
        connection.scalar(
            select(func.count())
            .select_from(Investigation)
            .where(Investigation.visitor_context_id == UUID(owner["visitor_context_id"]))
        )
        == 0
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"visitor_context_id": str(uuid4())},
        {"state_id": str(uuid4())},
        {"dataset_version_id": str(uuid4())},
        {"fixture_path": "other.json"},
    ],
)
def test_creation_rejects_owner_state_and_fixture_overrides(context, extra):
    client, _, _, _, _ = context
    response = create(client, **extra)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_stale_or_foreign_state_ids_cannot_target_workspace(context):
    client, _, _, _, _ = context
    workspace = create(client).json()
    url = f"/api/v1/investigations/{workspace['investigation_id']}/workspace"
    assert client.get(url + f"?state_id={uuid4()}").status_code == 422
    assert (
        client.get(f"/api/v1/investigations/{workspace['state_id']}/workspace").status_code == 404
    )
    assert client.get(url).json() == workspace


def test_missing_invalid_and_expired_sessions_do_not_expose_workspace(context):
    client, _, _, clock, _ = context
    workspace = create(client).json()
    path = f"/api/v1/investigations/{workspace['investigation_id']}/workspace"
    clock.now += timedelta(hours=24)
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert client.get(INCIDENT).status_code == 401
    assert create(client, workspace["incident"]["incident_id"]).status_code == 401
    response = client.get(path, headers={"Cookie": "__Host-opspilot_visitor=invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


def test_failure_after_graph_insert_rolls_back_all_workspace_rows(context, monkeypatch):
    import app.investigations as service

    client, connection, _, _, owner = context
    original = service.initialize_graph
    before = {
        model.__tablename__: connection.scalar(select(func.count()).select_from(model))
        for model in (Investigation, InvestigationState, WorkingDraft, ThreadState, StateSource)
    }

    def fail(db, investigation, catalog):
        original(db, investigation, catalog)
        raise RuntimeError("controlled failure after graph insertion")

    monkeypatch.setattr(service, "initialize_graph", fail)
    response = create(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "INITIALIZATION_FAILED"
    for model in (Investigation, InvestigationState, WorkingDraft, ThreadState, StateSource):
        assert (
            connection.scalar(select(func.count()).select_from(model))
            == before[model.__tablename__]
        )
    monkeypatch.setattr(service, "initialize_graph", original)
    assert create(client).status_code == 201


def test_session_expiring_during_initialization_rolls_back_before_commit(context, monkeypatch):
    import app.investigations as service

    client, connection, _, clock, owner = context
    original = service.initialize_graph

    def expire(db, investigation, catalog):
        original(db, investigation, catalog)
        clock.now += timedelta(days=1)

    monkeypatch.setattr(service, "initialize_graph", expire)
    response = create(client)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert (
        connection.scalar(
            select(func.count())
            .select_from(Investigation)
            .where(Investigation.visitor_context_id == UUID(owner["visitor_context_id"]))
        )
        == 0
    )


def test_workspace_uses_pinned_state_when_current_dataset_unavailable(context):
    client, _, app, _, _ = context
    workspace = create(client).json()
    app.state.catalog_error = APIError(
        503, "DATASET_UNAVAILABLE", "Configured dataset unavailable."
    )
    assert client.get(INCIDENT).status_code == 503
    assert create(client, workspace["incident"]["incident_id"]).json() == workspace
    assert (
        client.get(f"/api/v1/investigations/{workspace['investigation_id']}/workspace").json()
        == workspace
    )


def test_composite_fk_rejects_draft_pointing_to_other_investigation(context):
    client, connection, app, _, _ = context
    first = create(client).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        second = create(other).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        with pytest.raises(IntegrityError), db.begin():
            db.get(WorkingDraft, UUID(first["investigation_id"])).state_id = UUID(
                second["state_id"]
            )
            db.flush()
    fk = next(
        fk
        for fk in inspect(connection).get_foreign_keys("working_drafts")
        if fk["referred_table"] == "investigation_states"
    )
    assert fk["constrained_columns"] == ["state_id", "investigation_id"]
    assert fk["referred_columns"] == ["state_id", "investigation_id"]


def test_catalog_cannot_rewrite_registered_version(database):
    engine, settings = database
    initialize_catalog(engine, settings.current_dataset_version)
    with engine.connect() as connection:
        original = connection.scalar(
            select(DatasetVersion.fixture_digest).where(
                DatasetVersion.version_label == settings.current_dataset_version
            )
        )
    from app.catalog import register_catalog

    bundle, _ = load_fixture(settings.current_dataset_version)
    with pytest.raises(APIError):
        register_catalog(engine, bundle, "0" * 64)
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(DatasetVersion.fixture_digest).where(
                    DatasetVersion.version_label == settings.current_dataset_version
                )
            )
            == original
        )


@pytest.mark.parametrize(
    "mutation", ["missing_record", "duplicate_record", "bad_digest", "missing_source", "bad_case"]
)
def test_fixture_validation_rejects_incomplete_or_inconsistent_content(mutation):
    bundle, _ = load_fixture("synthetic-payments-v0.1")
    data = deepcopy(bundle.model_dump(mode="json"))
    if mutation == "missing_record":
        data["records"].pop()
    elif mutation == "duplicate_record":
        data["records"][-1] = data["records"][0]
    elif mutation == "bad_digest":
        data["records"][0]["payload"]["Alert title"] = "changed"
    elif mutation == "missing_source":
        data["sources"].pop()
    else:
        data["cases"][0]["evidence_record_ids"].append("SYN-NOT-CONSTRUCTED")
    with pytest.raises(ValueError):
        FixtureBundle.model_validate(data)


def test_unknown_configured_fixture_fails_without_fallback():
    with pytest.raises(APIError) as error:
        load_fixture("synthetic-payments-v999")
    assert error.value.code == "DATASET_UNAVAILABLE"


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_changed_fixture_file_fails_closed(tmp_path, monkeypatch, corrupt):
    import app.catalog as catalog

    monkeypatch.setattr(catalog, "BACKEND", tmp_path)
    if corrupt:
        directory = tmp_path / "fixtures"
        directory.mkdir()
        (directory / "synthetic-payments-v0.1.json").write_text("{}")
    with pytest.raises(APIError) as error:
        load_fixture("synthetic-payments-v0.1")
    assert error.value.code == "DATASET_UNAVAILABLE"


def test_concurrent_create_returns_one_committed_complete_workspace(database):
    _, settings = database
    first_app, second_app = create_app(settings), create_app(settings)
    with (
        TestClient(first_app, base_url="https://localhost:3000") as first,
        TestClient(second_app, base_url="https://localhost:3000") as second,
    ):
        bootstrap(first)
        second.cookies.update(first.cookies)
        incident_id = first.get(INCIDENT).json()["incident"]["incident_id"]
        barrier, lock = Barrier(2), Lock()
        matches = 0

        def synchronize_reads(conn, cursor, statement, parameters, context, executemany):
            nonlocal matches
            if (
                statement.startswith("SELECT investigations.")
                and "investigations.incident_id =" in statement
            ):
                with lock:
                    matches += 1
                    synchronize = matches <= 2
                if synchronize:
                    barrier.wait(timeout=5)

        event.listen(Engine, "after_cursor_execute", synchronize_reads)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                a, b = [
                    future.result(timeout=15)
                    for future in [
                        pool.submit(create, first, incident_id),
                        pool.submit(create, second, incident_id),
                    ]
                ]
        finally:
            event.remove(Engine, "after_cursor_execute", synchronize_reads)
        assert sorted([a.status_code, b.status_code]) == [200, 201]
        assert a.json() == b.json()
        assert len(a.json()["threads"]) == 2
        assert matches >= 3  # both missed initially, then the loser read the winner


def test_workspace_survives_application_and_engine_restart(database):
    _, settings = database
    with TestClient(create_app(settings), base_url="https://localhost:3000") as first:
        bootstrap(first)
        expected = create(first).json()
        jar = first.cookies
    with TestClient(create_app(settings), base_url="https://localhost:3000") as restarted:
        restarted.cookies.update(jar)
        response = restarted.get(f"/api/v1/investigations/{expected['investigation_id']}/workspace")
        assert response.status_code == 200
        assert response.json() == expected
