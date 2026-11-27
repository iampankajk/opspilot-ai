from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        echo=False,
        hide_parameters=True,
        pool_timeout=3,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=3000 -c lock_timeout=3000",
        },
    )


def expected_schema_revision() -> str:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


def check_database(engine: Engine, expected_revision: str) -> str | None:
    """Readiness reads only. It never creates tables, seeds data, or applies migrations."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names(schema="public"))
            required = {
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
            if not required <= tables:
                return "SCHEMA_NOT_READY"
            revisions = connection.execute(text("SELECT version_num FROM public.alembic_version"))
            if set(revisions.scalars()) != {expected_revision}:
                return "SCHEMA_NOT_READY"
    except SQLAlchemyError:
        return "DATABASE_UNAVAILABLE"
    return None
