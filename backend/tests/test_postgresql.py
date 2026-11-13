import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import check_database, expected_schema_revision
from app.main import create_app
from app.models import Incident, Investigation, VisitorContext


@pytest.fixture
def session(database):
    engine, _ = database
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


def visitor(**overrides):
    now = datetime.now(UTC)
    values = {
        "session_token_hash": hashlib.sha256(uuid4().bytes).digest(),
        "created_at": now,
        "expires_at": now + timedelta(hours=24),
    }
    return VisitorContext(**(values | overrides))


def test_upgrade_creates_only_first_boundary_and_matches_metadata(database):
    engine, _ = database
    assert set(inspect(engine).get_table_names(schema="public")) == {
        "alembic_version",
        "visitor_contexts",
        "dataset_versions",
        "incidents",
        "investigations",
    }
    assert check_database(engine, expected_schema_revision()) is None
    assert check_database(engine, "a_different_revision") == "SCHEMA_NOT_READY"


def test_real_health_reads_database_without_creating_rows(database):
    engine, settings = database
    with engine.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM visitor_contexts"))
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").status_code == 200
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM visitor_contexts")) == before


def test_owner_incident_pair_is_unique_but_visitors_are_independent(session):
    first, second = visitor(), visitor()
    incident = Incident(source_namespace="synthetic-test", source_incident_reference=str(uuid4()))
    session.add_all([first, second, incident])
    session.flush()
    session.add_all(
        [
            Investigation(
                visitor_context_id=owner.visitor_context_id, incident_id=incident.incident_id
            )
            for owner in (first, second)
        ]
    )
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            Investigation(
                visitor_context_id=first.visitor_context_id, incident_id=incident.incident_id
            )
        )
        session.flush()
    assert len(session.scalars(select(Investigation)).all()) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"session_token_hash": b"too-short"},
        {"expires_at": datetime(2000, 1, 1, tzinfo=UTC)},
        {"invalidated_at": datetime(2000, 1, 1, tzinfo=UTC)},
    ],
)
def test_database_rejects_invalid_session_storage(session, overrides):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(visitor(**overrides))
        session.flush()


def test_database_rejects_duplicate_credential_hash(session):
    first = visitor()
    session.add(first)
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(visitor(session_token_hash=first.session_token_hash))
        session.flush()


def test_database_rejects_missing_owner_or_incident(session):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Investigation(visitor_context_id=uuid4(), incident_id=uuid4()))
        session.flush()
