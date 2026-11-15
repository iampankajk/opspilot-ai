"""evidence request history

Revision ID: 0004_evidence_history
Revises: 0003_case_evidence
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_evidence_history"
down_revision = "0003_case_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_requests",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("thread_kind", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=True),
        sa.Column("initiator", sa.Text(), nullable=False),
        sa.Column("query_kind", sa.Text(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expected_draft_version", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("retry_of_request_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(status = 'pending' AND finished_at IS NULL) OR (status <> 'pending' AND "
            "finished_at IS NOT NULL AND finished_at >= requested_at)",
            name=op.f("ck_evidence_requests_finished"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','partial','failed','interrupted','stale')",
            name=op.f("ck_evidence_requests_status"),
        ),
        sa.CheckConstraint(
            "deadline_at > requested_at", name=op.f("ck_evidence_requests_deadline")
        ),
        sa.CheckConstraint(
            "expected_draft_version >= 0", name=op.f("ck_evidence_requests_version")
        ),
        sa.CheckConstraint(
            "retry_of_request_id <> request_id", name=op.f("ck_evidence_requests_not_self_retry")
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "retry_of_request_id"],
            ["evidence_requests.state_id", "evidence_requests.request_id"],
            name=op.f("fk_evidence_requests_state_id_evidence_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "thread_kind", "case_id"],
            ["case_threads.state_id", "case_threads.thread_kind", "case_threads.case_id"],
            name=op.f("fk_evidence_requests_state_id_case_threads"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "thread_kind"],
            ["thread_states.state_id", "thread_states.thread_kind"],
            name=op.f("fk_evidence_requests_state_id_thread_states"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("state_id", "request_id", name=op.f("pk_evidence_requests")),
    )
    op.create_table(
        "request_sources",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["state_id", "request_id"],
            ["evidence_requests.state_id", "evidence_requests.request_id"],
            name=op.f("fk_request_sources_state_id_evidence_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "source_key"],
            ["state_sources.state_id", "state_sources.source_key"],
            name=op.f("fk_request_sources_state_id_state_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "state_id", "request_id", "source_key", name=op.f("pk_request_sources")
        ),
    )
    op.create_table(
        "retrieval_results",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("execution_status", sa.Text(), nullable=False),
        sa.Column("availability", sa.Text(), nullable=False),
        sa.Column("match_status", sa.Text(), nullable=False),
        sa.Column("returned_count", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("completeness", sa.Text(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(execution_status = 'completed' AND match_status = 'matches' AND "
            "returned_count IS NOT NULL AND returned_count > 0) OR (execution_status "
            "= 'completed' AND match_status = 'no_matches' AND returned_count IS NOT "
            "NULL AND returned_count = 0) OR (match_status = 'not_evaluated' AND "
            "returned_count IS NULL)",
            name=op.f("ck_retrieval_results_count"),
        ),
        sa.CheckConstraint(
            "(execution_status = 'pending' AND completed_at IS NULL) OR "
            "(execution_status <> 'pending' AND completed_at IS NOT NULL)",
            name=op.f("ck_retrieval_results_finished"),
        ),
        sa.CheckConstraint(
            "availability IN ('included','not_included','not_constructed','unavailable')",
            name=op.f("ck_retrieval_results_availability"),
        ),
        sa.CheckConstraint(
            "completeness IN "
            "('unverified','known_partial','verified_for_stated_scope','not_applicable')",
            name=op.f("ck_retrieval_results_completeness"),
        ),
        sa.CheckConstraint(
            "execution_status IN ('pending','completed','failed','interrupted')",
            name=op.f("ck_retrieval_results_execution"),
        ),
        sa.CheckConstraint(
            "match_status IN ('matches','no_matches','not_evaluated')",
            name=op.f("ck_retrieval_results_match"),
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "request_id", "source_key"],
            [
                "request_sources.state_id",
                "request_sources.request_id",
                "request_sources.source_key",
            ],
            name=op.f("fk_retrieval_results_state_id_request_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "state_id", "request_id", "source_key", name=op.f("pk_retrieval_results")
        ),
    )
    op.create_table(
        "retrieval_result_records",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("evidence_record_id", sa.Text(), nullable=False),
        sa.Column("match_basis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["state_id", "evidence_record_id", "source_key"],
            [
                "evidence_records.state_id",
                "evidence_records.evidence_record_id",
                "evidence_records.source_key",
            ],
            name=op.f("fk_retrieval_result_records_state_id_evidence_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "request_id", "source_key"],
            [
                "retrieval_results.state_id",
                "retrieval_results.request_id",
                "retrieval_results.source_key",
            ],
            name=op.f("fk_retrieval_result_records_state_id_retrieval_results"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "state_id",
            "request_id",
            "source_key",
            "evidence_record_id",
            name=op.f("pk_retrieval_result_records"),
        ),
    )


def downgrade() -> None:
    op.drop_table("retrieval_result_records")
    op.drop_table("retrieval_results")
    op.drop_table("request_sources")
    op.drop_table("evidence_requests")
