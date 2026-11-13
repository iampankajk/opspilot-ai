"""Approved stage 002: durable working state, two thread kinds, and source coverage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_working_workspace"
down_revision = "0001_ownership_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_states",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("incident_context", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("state_id", name="pk_investigation_states"),
        sa.UniqueConstraint(
            "state_id", "investigation_id", name="uq_investigation_states_state_id"
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.investigation_id"],
            name="fk_investigation_states_investigation_id_investigations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.dataset_version_id"],
            name="fk_investigation_states_dataset_version_id_dataset_versions",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_investigation_states_investigation_id", "investigation_states", ["investigation_id"]
    )
    op.create_table(
        "working_drafts",
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_unversioned_changes", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "persisted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("investigation_id", name="pk_working_drafts"),
        sa.UniqueConstraint("state_id", name="uq_working_drafts_state_id"),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.investigation_id"],
            name="fk_working_drafts_investigation_id_investigations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "investigation_id"],
            ["investigation_states.state_id", "investigation_states.investigation_id"],
            name="fk_working_drafts_state_id_investigation_states",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "draft_version >= 0", name=op.f("ck_working_drafts_nonnegative_version")
        ),
    )
    op.create_table(
        "thread_states",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("thread_kind", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("unresolved_questions", postgresql.JSONB(), nullable=False),
        sa.Column("presentation", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("state_id", "thread_kind", name="pk_thread_states"),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["investigation_states.state_id"],
            name="fk_thread_states_state_id_investigation_states",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "thread_kind IN ('payment_failures', 'possible_duplicates')",
            name=op.f("ck_thread_states_thread_kind"),
        ),
    )
    op.create_table(
        "state_sources",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_category", sa.Text(), nullable=False),
        sa.Column("availability", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("completeness", sa.Text(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("state_id", "source_key", name="pk_state_sources"),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["investigation_states.state_id"],
            name="fk_state_sources_state_id_investigation_states",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "availability IN ('included', 'not_included', 'not_constructed', 'unavailable')",
            name=op.f("ck_state_sources_availability"),
        ),
        sa.CheckConstraint(
            "completeness IN ('unverified', 'known_partial', "
            "'verified_for_stated_scope', 'not_applicable')",
            name=op.f("ck_state_sources_completeness"),
        ),
    )


def downgrade() -> None:
    # Destructive: requires impact review and explicit approval against stored work.
    op.drop_table("state_sources")
    op.drop_table("thread_states")
    op.drop_table("working_drafts")
    op.drop_index("ix_investigation_states_investigation_id", table_name="investigation_states")
    op.drop_table("investigation_states")
