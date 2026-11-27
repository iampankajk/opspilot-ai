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


def test_upgrade_creates_five_boundaries_and_matches_metadata(database):
    engine, _ = database
    assert set(inspect(engine).get_table_names(schema="public")) == {
        "alembic_version",
        "visitor_contexts",
        "workspace_actors",
        "actor_sessions",
        "dataset_versions",
        "incidents",
        "investigations",
        "investigation_states",
        "working_drafts",
        "thread_states",
        "state_sources",
        "evidence_records",
        "payment_cases",
        "case_threads",
        "case_evidence_links",
        "evidence_relationships",
        "evidence_requests",
        "request_sources",
        "retrieval_results",
        "retrieval_result_records",
        "ai_generation_requests",
        "findings",
        "finding_cases",
        "ai_proposals",
        "evidence_citations",
        "assessment_result_refs",
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
    assert (
        len(
            session.scalars(
                select(Investigation).where(
                    Investigation.visitor_context_id.in_(
                        [first.visitor_context_id, second.visitor_context_id]
                    )
                )
            ).all()
        )
        == 2
    )


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


def test_all_migrations_upgrade_an_empty_schema_without_touching_public(database):
    from io import StringIO
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    engine, _ = database
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    # Run the entire chain against a new schema in a transaction, then roll it all back.
    # No preexisting data or tables are deleted and no downgrade is used.
    ddl = output.getvalue().replace("BEGIN;", "").replace("COMMIT;", "")
    schema = "migration_check_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            connection.exec_driver_sql(ddl)
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0006_actor_auth"
            )
            from app.models import Base

            assert set(inspect(connection).get_table_names(schema=schema)) == set(
                Base.metadata.tables
            ) | {"alembic_version"}
        finally:
            transaction.rollback()
    assert schema not in inspect(engine).get_schema_names()


def test_0006_actor_auth_backfills_existing_visitors_and_enforces_composite_fk(database):
    from io import StringIO
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    engine, _ = database
    ddl_0005_buf = StringIO()
    config_0005 = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=ddl_0005_buf
    )
    command.upgrade(config_0005, "0005_ai_findings", sql=True)
    ddl_0005 = ddl_0005_buf.getvalue().replace("BEGIN;", "").replace("COMMIT;", "")

    ddl_0006_buf = StringIO()
    config_0006 = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=ddl_0006_buf
    )
    command.upgrade(config_0006, "0005_ai_findings:0006_actor_auth", sql=True)
    ddl_0006 = ddl_0006_buf.getvalue().replace("BEGIN;", "").replace("COMMIT;", "")

    schema = "migration_0006_backfill_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            connection.exec_driver_sql(ddl_0005)

            vc1_id, vc2_id = uuid4(), uuid4()
            now = datetime.now(UTC)
            token1_hash = hashlib.sha256(b"legacy-token-1").digest()
            token2_hash = hashlib.sha256(b"legacy-token-2").digest()
            connection.execute(
                text(
                    "INSERT INTO visitor_contexts "
                    "(visitor_context_id, created_at, session_token_hash, "
                    "expires_at, invalidated_at) "
                    "VALUES (:id1, :c1, :h1, :e1, NULL), (:id2, :c2, :h2, :e2, :inv2)"
                ),
                {
                    "id1": vc1_id,
                    "c1": now,
                    "h1": token1_hash,
                    "e1": now + timedelta(hours=24),
                    "id2": vc2_id,
                    "c2": now - timedelta(hours=2),
                    "h2": token2_hash,
                    "e2": now + timedelta(hours=22),
                    "inv2": now - timedelta(hours=1),
                },
            )

            connection.exec_driver_sql(ddl_0006)
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0006_actor_auth"
            )

            actors = connection.execute(
                text(
                    "SELECT actor_id, visitor_context_id, actor_ref, display_name, role, "
                    "access_code_hash, disabled_at FROM workspace_actors ORDER BY created_at DESC"
                )
            ).all()
            assert len(actors) == 2
            by_ws = {row.visitor_context_id: row for row in actors}
            assert by_ws[vc1_id].actor_ref == "ops-engineer-1"
            assert by_ws[vc1_id].display_name == "Maya Lin"
            assert by_ws[vc1_id].role == "engineer"
            assert by_ws[vc1_id].access_code_hash is None
            assert by_ws[vc1_id].disabled_at is None
            assert by_ws[vc2_id].role == "engineer"

            sessions = connection.execute(
                text(
                    "SELECT visitor_context_id, actor_id, session_token_hash, "
                    "expires_at, invalidated_at FROM actor_sessions"
                )
            ).all()
            assert len(sessions) == 2
            sess_by_ws = {row.visitor_context_id: row for row in sessions}
            assert sess_by_ws[vc1_id].actor_id == by_ws[vc1_id].actor_id
            assert bytes(sess_by_ws[vc1_id].session_token_hash) == token1_hash
            assert sess_by_ws[vc1_id].invalidated_at is None
            assert sess_by_ws[vc2_id].actor_id == by_ws[vc2_id].actor_id
            assert bytes(sess_by_ws[vc2_id].session_token_hash) == token2_hash
            assert sess_by_ws[vc2_id].invalidated_at is not None

            # Verify composite FK rejects cross-workspace (vc1, vc2_actor_id) session insert.
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO actor_sessions "
                        "(session_id, visitor_context_id, actor_id, session_token_hash, "
                        "created_at, expires_at) "
                        "VALUES (:sid, :ws, :aid, :tok, :c, :e)"
                    ),
                    {
                        "sid": uuid4(),
                        "ws": vc1_id,
                        "aid": by_ws[vc2_id].actor_id,
                        "tok": hashlib.sha256(b"cross-workspace-forged").digest(),
                        "c": now,
                        "e": now + timedelta(hours=1),
                    },
                )
            savepoint.rollback()
        finally:
            transaction.rollback()
    assert schema not in inspect(engine).get_schema_names()
