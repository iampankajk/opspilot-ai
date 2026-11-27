"""actor auth

Revision ID: 0006_actor_auth
Revises: 0005_ai_findings
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_actor_auth"
down_revision = "0005_ai_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_actors",
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_context_id", sa.Uuid(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("access_code_hash", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "actor_ref ~ '^[a-z0-9][a-z0-9._-]{1,63}$'",
            name=op.f("ck_workspace_actors_actor_ref"),
        ),
        sa.CheckConstraint(
            "btrim(display_name) <> '' AND length(display_name) <= 120",
            name=op.f("ck_workspace_actors_display_name"),
        ),
        sa.CheckConstraint("role IN ('engineer', 'lead')", name=op.f("ck_workspace_actors_role")),
        sa.CheckConstraint(
            "access_code_hash IS NULL OR octet_length(access_code_hash) = 32",
            name=op.f("ck_workspace_actors_access_code_hash_length"),
        ),
        sa.CheckConstraint(
            "disabled_at IS NULL OR disabled_at >= created_at",
            name=op.f("ck_workspace_actors_disabled_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_context_id"],
            ["visitor_contexts.visitor_context_id"],
            name=op.f("fk_workspace_actors_visitor_context_id_visitor_contexts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("actor_id", name=op.f("pk_workspace_actors")),
        sa.UniqueConstraint(
            "visitor_context_id", "actor_ref", name="uq_workspace_actors_workspace_ref"
        ),
        sa.UniqueConstraint(
            "visitor_context_id", "actor_id", name="uq_workspace_actors_workspace_actor"
        ),
        sa.UniqueConstraint("actor_id", "role", name="uq_workspace_actors_actor_role"),
    )
    op.create_index(
        "ix_workspace_actors_visitor_context_id",
        "workspace_actors",
        ["visitor_context_id"],
        unique=False,
    )
    op.create_index(
        "uq_workspace_actors_access_code_hash",
        "workspace_actors",
        ["access_code_hash"],
        unique=True,
        postgresql_where=sa.text("access_code_hash IS NOT NULL"),
    )
    op.create_table(
        "actor_sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_context_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("session_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(session_token_hash) = 32",
            name=op.f("ck_actor_sessions_token_hash_length"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_actor_sessions_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "invalidated_at IS NULL OR invalidated_at >= created_at",
            name=op.f("ck_actor_sessions_invalidation_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_context_id", "actor_id"],
            ["workspace_actors.visitor_context_id", "workspace_actors.actor_id"],
            name=op.f("fk_actor_sessions_visitor_context_id_workspace_actors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_actor_sessions")),
        sa.UniqueConstraint(
            "session_token_hash", name=op.f("uq_actor_sessions_session_token_hash")
        ),
    )
    op.create_index(
        "ix_actor_sessions_workspace_actor",
        "actor_sessions",
        ["visitor_context_id", "actor_id"],
        unique=False,
    )
    op.alter_column(
        "visitor_contexts",
        "session_token_hash",
        existing_type=sa.LargeBinary(),
        nullable=True,
    )
    # Idempotently backfill pre-existing visitor workspaces into engineer-only actors/sessions.
    op.execute(
        sa.text(
            """
            INSERT INTO workspace_actors (
                actor_id,
                visitor_context_id,
                actor_ref,
                display_name,
                role,
                access_code_hash,
                created_at
            )
            SELECT
                gen_random_uuid(),
                vc.visitor_context_id,
                'ops-engineer-1',
                'Maya Lin',
                'engineer',
                NULL,
                vc.created_at
            FROM visitor_contexts vc
            WHERE NOT EXISTS (
                SELECT 1
                FROM workspace_actors wa
                WHERE wa.visitor_context_id = vc.visitor_context_id
            )
            ON CONFLICT DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO actor_sessions (
                session_id,
                visitor_context_id,
                actor_id,
                session_token_hash,
                created_at,
                expires_at,
                invalidated_at
            )
            SELECT
                gen_random_uuid(),
                vc.visitor_context_id,
                wa.actor_id,
                vc.session_token_hash,
                vc.created_at,
                vc.expires_at,
                vc.invalidated_at
            FROM visitor_contexts vc
            JOIN workspace_actors wa
                ON wa.visitor_context_id = vc.visitor_context_id
                AND wa.actor_ref = 'ops-engineer-1'
            WHERE vc.session_token_hash IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM actor_sessions s
                WHERE s.session_token_hash = vc.session_token_hash
            )
            ON CONFLICT (session_token_hash) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.alter_column(
        "visitor_contexts",
        "session_token_hash",
        existing_type=sa.LargeBinary(),
        nullable=False,
    )
    op.drop_index("ix_actor_sessions_workspace_actor", table_name="actor_sessions")
    op.drop_table("actor_sessions")
    op.drop_index("uq_workspace_actors_access_code_hash", table_name="workspace_actors")
    op.drop_index("ix_workspace_actors_visitor_context_id", table_name="workspace_actors")
    op.drop_table("workspace_actors")
