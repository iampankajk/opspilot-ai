# ruff: noqa: F811 -- pytest injects the imported shared fixture.
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_investigations import bootstrap, create
from test_investigations import context as case_context  # noqa: F401, F811

from app.catalog import load_fixture
from app.main import create_app
from app.materialization import GRAPH_MODELS
from app.models import (
    CaseEvidenceLink,
    CaseThread,
    EvidenceRecord,
    EvidenceRelationship,
    Investigation,
    InvestigationState,
    PaymentCase,
    StateSource,
    WorkingDraft,
)


def listing(client, workspace, thread="payment_failures", **query):
    return client.get(
        f"/api/v1/investigations/{workspace['investigation_id']}/threads/{thread}/cases",
        params={"state_id": workspace["state_id"]} | query,
    )


def counts(connection, state_id):
    return [
        connection.scalar(select(func.count()).select_from(model).where(model.state_id == state_id))
        for model in GRAPH_MODELS
    ]


def legacy_workspace(client, monkeypatch):
    # Reproduce the approved stage-002 initializer without deleting any persisted data.
    with monkeypatch.context() as patch:
        patch.setattr("app.investigations.materialize_state", lambda *args, **kwargs: False)
        result = create(client)
        assert result.status_code == 201
        return result.json()


def test_persists_exact_records_mappings_and_source_limitations(case_context):
    client, connection, _, _, _ = case_context
    workspace = create(client).json()
    state = UUID(workspace["state_id"])
    assert counts(connection, state) == [14, 2, 2, 11, 14]
    bundle, _ = load_fixture("synthetic-payments-v0.1")
    with Session(bind=connection) as db:
        for source in bundle.records:
            saved = db.get(EvidenceRecord, (state, source.record_id))
            assert saved.payload == source.payload
            assert saved.raw_markdown == source.raw_markdown
            assert saved.source_digest == source.payload_digest
            assert saved.source_key == source.source_key
        for case in bundle.cases:
            actual = set(
                db.scalars(
                    select(CaseEvidenceLink.evidence_record_id).where(
                        CaseEvidenceLink.state_id == state,
                        CaseEvidenceLink.case_id == case.case_id,
                    )
                )
            )
            assert actual == set(case.evidence_record_ids)
        stripe = db.get(StateSource, (state, "stripe"))
        assert stripe.completeness == "unverified"
        assert db.get(InvestigationState, state).limitations == bundle.declared_gaps
        relation = db.get(EvidenceRelationship, (state, "duplicate-attempts-idempotency"))
        assert relation.category == "field_match"
        assert "not proof" in relation.explanation
        assert relation.matched_fields["matching_identifiers"] == ["SYN-IDEM-DUP-001"]
        deployment = db.get(EvidenceRelationship, (state, "deployment-failure-context"))
        assert deployment.category == "temporal_context"
        assert "No deployment success" in deployment.limitations[0]


def test_case_contract_keeps_reported_and_candidate_values_distinct(case_context):
    client, _, _, _, _ = case_context
    workspace = create(client).json()
    failure = listing(client, workspace)
    assert failure.status_code == 200
    assert failure.headers["cache-control"] == "no-store"
    body = failure.json()
    assert {k: body[k] for k in ("investigation_id", "state_id", "draft_version")} == {
        k: workspace[k] for k in ("investigation_id", "state_id", "draft_version")
    }
    case = body["cases"][0]
    assert case["case_id"] == "case-failure-001"
    assert case["reported_money"] == {"amount": "48.00", "currency": "SGD"}
    assert case["reported_order_ref"] == "SYN-ORD-001"
    assert case["reported_at"]["precision"] == "minute"
    assert case["reported_at"]["utc_lower"] == "2026-10-20T02:31:00Z"
    assert case["payment_state"]["label"] == "Outcome unknown after timeout"
    assert case["investigation_progress"] == "not_started"
    duplicate = listing(client, workspace, "possible_duplicates").json()["cases"]
    assert len(duplicate) == 1
    case = duplicate[0]
    assert case["case_id"] == "case-duplicate-001"
    assert case["reported_order_ref"] is None and case["payment_state"] is None
    assert case["reported_money"] == {"amount": "120.00", "currency": "SGD"}
    assert case["related_order_refs"] == [
        {
            "value": "SYN-ORD-002",
            "association": "candidate",
            "basis_record_id": "SYN-ZD-HANDOFF-001",
        }
    ]
    assert "reports" in case["reported_issue"]


@pytest.mark.parametrize("entrypoint", ["cases", "workspace", "resume"])
def test_legacy_materialization_preserves_owned_draft_and_increments_once(
    case_context,
    monkeypatch,
    entrypoint,
):
    client, connection, _, _, owner = case_context
    old = legacy_workspace(client, monkeypatch)
    state, investigation = UUID(old["state_id"]), UUID(old["investigation_id"])
    assert counts(connection, state) == [0] * 5
    if entrypoint == "cases":
        response = listing(client, old)
    elif entrypoint == "workspace":
        response = client.get(f"/api/v1/investigations/{investigation}/workspace")
    else:
        response = create(client)
    assert response.status_code == 200
    assert response.json()["state_id"] == old["state_id"]
    assert response.json()["draft_version"] == 1
    for _ in range(2):
        assert listing(client, old).json()["draft_version"] == 1
        assert create(client).json()["draft_version"] == 1
    assert counts(connection, state) == [14, 2, 2, 11, 14]
    with Session(bind=connection) as db:
        assert (
            str(db.get(Investigation, investigation).visitor_context_id)
            == owner["visitor_context_id"]
        )
        assert (
            str(db.get(InvestigationState, state).dataset_version_id)
            == old["dataset_version"]["dataset_version_id"]
        )
        assert db.get(WorkingDraft, investigation).has_unversioned_changes


def test_legacy_uses_pinned_dataset_even_when_current_catalog_unavailable(
    case_context, monkeypatch
):
    client, _, app, _, _ = case_context
    old = legacy_workspace(client, monkeypatch)
    from app.catalog import dataset_unavailable

    app.state.catalog_error = dataset_unavailable()
    assert listing(client, old).status_code == 200


def test_materialized_reads_use_saved_data_without_fixture_file(
    case_context, monkeypatch, tmp_path
):
    client, _, _, _, _ = case_context
    workspace = create(client).json()
    expected = listing(client, workspace).json()
    monkeypatch.setattr("app.catalog.BACKEND", tmp_path)
    assert listing(client, workspace).json() == expected


def test_legacy_missing_pinned_fixture_fails_without_partial_data(
    case_context, monkeypatch, tmp_path
):
    client, connection, _, _, _ = case_context
    old = legacy_workspace(client, monkeypatch)
    monkeypatch.setattr("app.catalog.BACKEND", tmp_path)
    response = listing(client, old)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert counts(connection, UUID(old["state_id"])) == [0] * 5


def test_independent_visitors_and_foreign_state_are_isolated(case_context):
    client, connection, app, _, _ = case_context
    first = create(client).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        second = create(other).json()
        assert first["state_id"] != second["state_id"]
        for workspace in (first, second):
            assert counts(connection, UUID(workspace["state_id"])) == [14, 2, 2, 11, 14]
        foreign = listing(other, first, state_id=second["state_id"])
        missing = listing(other, first | {"investigation_id": str(uuid4())})
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["error"]["message"] == missing.json()["error"]["message"]
        assert listing(client, first, state_id=second["state_id"]).status_code == 409
        assert listing(other, second).status_code == 200


@pytest.mark.parametrize(
    "thread,query,status",
    [
        ("not_a_thread", {}, 422),
        ("payment_failures", {"state_id": "invalid"}, 422),
        ("payment_failures", {"state_id": str(uuid4())}, 409),
        ("payment_failures", {"case_id": "CASE-DUP-001"}, 422),
        ("payment_failures", {"visitor_context_id": str(uuid4())}, 422),
    ],
)
def test_invalid_thread_state_case_or_owner_override(case_context, thread, query, status):
    client, _, _, _, _ = case_context
    workspace = create(client).json()
    response = listing(client, workspace, thread, **query)
    assert response.status_code == status
    assert "cases" not in response.json()


def test_state_is_required_and_case_detail_remains_unimplemented(case_context):
    client, _, _, _, _ = case_context
    workspace = create(client).json()
    path = f"/api/v1/investigations/{workspace['investigation_id']}/threads/payment_failures/cases"
    assert client.get(path).status_code == 422
    assert (
        client.get(path + "/CASE-DUP-001", params={"state_id": workspace["state_id"]}).status_code
        == 404
    )


def test_missing_invalid_and_expired_sessions_cannot_read_cases(case_context):
    client, _, app, clock, _ = case_context
    workspace = create(client).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        assert listing(other, workspace).json()["error"]["code"] == "SESSION_REQUIRED"
        other.cookies.set("__Host-opspilot_visitor", "x" * 43, domain="localhost.local", path="/")
        assert listing(other, workspace).json()["error"]["code"] == "SESSION_INVALID"
    clock.now += timedelta(hours=24)
    response = listing(client, workspace)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_failure_after_partial_insert_rolls_back_legacy_state_and_draft(case_context, monkeypatch):
    client, connection, _, _, _ = case_context
    workspace = legacy_workspace(client, monkeypatch)
    import app.materialization as materialization

    original = materialization.persist_graph

    def fail(db, graph):
        db.add_all(EvidenceRecord(**row) for row in graph[EvidenceRecord])
        db.flush()
        db.add_all(PaymentCase(**row) for row in graph[PaymentCase])
        db.flush()
        raise RuntimeError("injected materialization failure")

    monkeypatch.setattr(materialization, "persist_graph", fail)
    assert listing(client, workspace).status_code == 503
    assert counts(connection, UUID(workspace["state_id"])) == [0] * 5
    with Session(bind=connection) as db:
        assert db.get(WorkingDraft, UUID(workspace["investigation_id"])).draft_version == 0
    monkeypatch.setattr(materialization, "persist_graph", original)
    assert listing(client, workspace).status_code == 200


def test_corrupt_existing_graph_is_rejected_without_overwriting(case_context):
    client, connection, _, _, _ = case_context
    workspace = create(client).json()
    state = UUID(workspace["state_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        db.get(PaymentCase, (state, "case-duplicate-001")).reported_order_ref = "unsupported"
    assert listing(client, workspace).status_code == 503
    with Session(bind=connection) as db:
        assert (
            db.get(PaymentCase, (state, "case-duplicate-001")).reported_order_ref == "unsupported"
        )


@pytest.mark.parametrize(
    "model,changes",
    [
        (CaseThread, {"thread_kind": "not_a_thread"}),
        (CaseThread, {"case_id": "missing"}),
        (CaseEvidenceLink, {"evidence_record_id": "missing"}),
        (CaseEvidenceLink, {"basis_record_id": "missing"}),
        (EvidenceRelationship, {"basis_record_id": "missing"}),
        (EvidenceRelationship, {"from_record_id": "missing"}),
        (EvidenceRelationship, {"to_record_id": "missing"}),
        (PaymentCase, {"primary_report_record_id": "missing"}),
        (EvidenceRecord, {"source_key": "missing"}),
    ],
)
def test_database_enforces_composite_scope(case_context, model, changes):
    client, connection, _, _, _ = case_context
    workspace = create(client).json()
    state = UUID(workspace["state_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        row = db.scalar(select(model).where(model.state_id == state))
        with pytest.raises(IntegrityError), db.begin_nested():
            for field, value in changes.items():
                setattr(row, field, value)
            db.flush()
    for fk in inspect(connection).get_foreign_keys(model.__tablename__):
        assert "state_id" in fk["constrained_columns"]
        assert "state_id" in fk["referred_columns"]


def test_cases_survive_new_application_and_engine(database):
    _, settings = database
    with TestClient(create_app(settings), base_url="https://localhost:3000") as first:
        bootstrap(first)
        workspace = create(first).json()
        expected = listing(first, workspace).json()
        jar = first.cookies
    with TestClient(create_app(settings), base_url="https://localhost:3000") as restarted:
        restarted.cookies.update(jar)
        assert listing(restarted, workspace).json() == expected


def test_concurrent_legacy_materialization_advances_once(database, monkeypatch):
    engine, settings = database
    with (
        TestClient(create_app(settings), base_url="https://localhost:3000") as first,
        TestClient(create_app(settings), base_url="https://localhost:3000") as second,
    ):
        bootstrap(first)
        workspace = legacy_workspace(first, monkeypatch)
        second.cookies.update(first.cookies)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(listing, client, workspace) for client in (first, second)]
            responses = [future.result(timeout=15) for future in futures]
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
        assert responses[0].json()["draft_version"] == 1
        with engine.connect() as connection:
            assert counts(connection, UUID(workspace["state_id"])) == [14, 2, 2, 11, 14]


def test_foreign_only_record_cannot_satisfy_same_state_basis(case_context):
    client, connection, app, _, _ = case_context
    first = create(client).json()
    with TestClient(app, base_url="https://localhost:3000") as other:
        bootstrap(other)
        second = create(other).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        row = db.get(EvidenceRecord, (UUID(second["state_id"]), "SYN-ZD-TICKET-001"))
        values = {
            column.name: getattr(row, column.name) for column in EvidenceRecord.__table__.columns
        }
        values["evidence_record_id"] = "foreign-only-record"
        db.add(EvidenceRecord(**values))
        db.flush()
        link = db.get(
            CaseEvidenceLink, (UUID(first["state_id"]), "case-failure-001", "SYN-ZD-TICKET-001")
        )
        with pytest.raises(IntegrityError), db.begin_nested():
            link.basis_record_id = "foreign-only-record"
            db.flush()


def test_expiry_during_materialization_rolls_back_before_commit(case_context, monkeypatch):
    client, connection, _, clock, _ = case_context
    workspace = legacy_workspace(client, monkeypatch)
    import app.materialization as materialization

    original = materialization.persist_graph

    def expire(db, graph):
        original(db, graph)
        clock.now += timedelta(hours=24)

    monkeypatch.setattr(materialization, "persist_graph", expire)
    response = listing(client, workspace)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert counts(connection, UUID(workspace["state_id"])) == [0] * 5


def test_failed_new_initialization_leaves_no_partial_graph(case_context, monkeypatch):
    client, connection, _, _, _ = case_context
    models = (*GRAPH_MODELS, Investigation, InvestigationState, WorkingDraft, StateSource)
    before = [connection.scalar(select(func.count()).select_from(model)) for model in models]

    def fail(db, graph):
        db.add_all(EvidenceRecord(**row) for row in graph[EvidenceRecord])
        db.flush()
        raise RuntimeError("injected initialization failure")

    monkeypatch.setattr("app.materialization.persist_graph", fail)
    assert create(client).status_code == 503
    after = [connection.scalar(select(func.count()).select_from(model)) for model in models]
    assert before == after
