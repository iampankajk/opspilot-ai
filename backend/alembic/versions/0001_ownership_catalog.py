"""First approved boundary: ownership and catalog only. No fixture payloads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_ownership_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visitor_contexts",
        sa.Column("visitor_context_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("session_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("visitor_context_id", name="pk_visitor_contexts"),
        sa.UniqueConstraint("session_token_hash", name="uq_visitor_contexts_session_token_hash"),
        sa.CheckConstraint(
            "octet_length(session_token_hash) = 32",
            name=op.f("ck_visitor_contexts_token_hash_length"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_visitor_contexts_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "invalidated_at IS NULL OR invalidated_at >= created_at",
            name=op.f("ck_visitor_contexts_invalidation_after_creation"),
        ),
    )
    op.create_table(
        "dataset_versions",
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.Text(), nullable=False),
        sa.Column("fixture_digest", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("dataset_version_id", name="pk_dataset_versions"),
        sa.UniqueConstraint("version_label", name="uq_dataset_versions_version_label"),
        sa.CheckConstraint(
            "btrim(version_label) <> ''", name=op.f("ck_dataset_versions_version_label_nonblank")
        ),
        sa.CheckConstraint(
            "fixture_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_dataset_versions_digest_sha256_hex")
        ),
    )
    op.create_table(
        "incidents",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("source_namespace", sa.Text(), nullable=False),
        sa.Column("source_incident_reference", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("incident_id", name="pk_incidents"),
        sa.UniqueConstraint(
            "source_namespace", "source_incident_reference", name="uq_incidents_source_namespace"
        ),
        sa.CheckConstraint(
            "btrim(source_namespace) <> ''", name=op.f("ck_incidents_source_namespace_nonblank")
        ),
        sa.CheckConstraint(
            "btrim(source_incident_reference) <> ''",
            name=op.f("ck_incidents_source_reference_nonblank"),
        ),
    )
    op.create_table(
        "investigations",
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_context_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("investigation_id", name="pk_investigations"),
        sa.ForeignKeyConstraint(
            ["visitor_context_id"],
            ["visitor_contexts.visitor_context_id"],
            name="fk_investigations_visitor_context_id_visitor_contexts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.incident_id"],
            name="fk_investigations_incident_id_incidents",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "visitor_context_id", "incident_id", name="uq_investigations_visitor_context_id"
        ),
    )
    op.create_index(
        "ix_investigations_visitor_context_id", "investigations", ["visitor_context_id"]
    )
    op.create_index("ix_investigations_incident_id", "investigations", ["incident_id"])


def downgrade() -> None:
    # Destructive: review impact and obtain approval before executing against stored work.
    op.drop_index("ix_investigations_incident_id", table_name="investigations")
    op.drop_index("ix_investigations_visitor_context_id", table_name="investigations")
    op.drop_table("investigations")
    op.drop_table("incidents")
    op.drop_table("dataset_versions")
    op.drop_table("visitor_contexts")
