"""case evidence graph

Revision ID: 0003_case_evidence
Revises: 0002_working_workspace
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_case_evidence"
down_revision = "0002_working_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_records",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_record_id", sa.Text(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("record_type", sa.Text(), nullable=False),
        sa.Column("source_record_reference", sa.Text(), nullable=True),
        sa.Column("fixture_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_markdown", sa.Text(), nullable=False),
        sa.Column("timestamps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "evidence_record_id ~ '^[A-Za-z0-9._:-]{1,128}$'",
            name=op.f("ck_evidence_records_local_id"),
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "source_key"],
            ["state_sources.state_id", "state_sources.source_key"],
            name=op.f("fk_evidence_records_state_id_state_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("state_id", "evidence_record_id", name=op.f("pk_evidence_records")),
        sa.UniqueConstraint(
            "state_id",
            "evidence_record_id",
            "source_key",
            name=op.f("uq_evidence_records_state_id"),
        ),
    )
    op.create_table(
        "evidence_relationships",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_id", sa.Text(), nullable=False),
        sa.Column("from_record_id", sa.Text(), nullable=False),
        sa.Column("to_record_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("matched_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("basis_record_id", sa.Text(), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "category IN ('direct_ref_match', 'documented_lookup', 'field_match', "
            "'temporal_context', 'unverified')",
            name=op.f("ck_evidence_relationships_category"),
        ),
        sa.CheckConstraint(
            "relationship_id ~ '^[A-Za-z0-9._:-]{1,128}$'",
            name=op.f("ck_evidence_relationships_local_id"),
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "basis_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_basis",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "from_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_from_record",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "to_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_to_record",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "state_id", "relationship_id", name=op.f("pk_evidence_relationships")
        ),
    )
    op.create_table(
        "payment_cases",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("case_reference", sa.Text(), nullable=False),
        sa.Column("primary_report_record_id", sa.Text(), nullable=False),
        sa.Column("customer_ref", sa.Text(), nullable=True),
        sa.Column("reported_order_ref", sa.Text(), nullable=True),
        sa.Column("related_order_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reported_issue", sa.Text(), nullable=False),
        sa.Column("reported_amount", sa.Numeric(), nullable=True),
        sa.Column("reported_currency", sa.Text(), nullable=True),
        sa.Column("reported_at", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "payment_state",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("field_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "case_id ~ '^[A-Za-z0-9._:-]{1,128}$'", name=op.f("ck_payment_cases_local_id")
        ),
        sa.CheckConstraint(
            "(reported_amount IS NULL) = (reported_currency IS NULL)",
            name=op.f("ck_payment_cases_money_pair"),
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "primary_report_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name=op.f("fk_payment_cases_state_id_evidence_records"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("state_id", "case_id", name=op.f("pk_payment_cases")),
        sa.UniqueConstraint("state_id", "case_reference", name=op.f("uq_payment_cases_state_id")),
    )
    op.create_table(
        "case_evidence_links",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("evidence_record_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("matched_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("basis_record_id", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "category IN ('direct_ref_match', 'documented_lookup', 'field_match', "
            "'temporal_context', 'unverified')",
            name=op.f("ck_case_evidence_links_category"),
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "basis_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_case_evidence_links_basis",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "case_id"],
            ["payment_cases.state_id", "payment_cases.case_id"],
            name=op.f("fk_case_evidence_links_state_id_payment_cases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "evidence_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_case_evidence_links_record",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "state_id", "case_id", "evidence_record_id", name=op.f("pk_case_evidence_links")
        ),
    )
    op.create_table(
        "case_threads",
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("thread_kind", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["state_id", "case_id"],
            ["payment_cases.state_id", "payment_cases.case_id"],
            name=op.f("fk_case_threads_state_id_payment_cases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["state_id", "thread_kind"],
            ["thread_states.state_id", "thread_states.thread_kind"],
            name=op.f("fk_case_threads_state_id_thread_states"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("state_id", "thread_kind", "case_id", name=op.f("pk_case_threads")),
    )


def downgrade() -> None:
    op.drop_table("case_threads")
    op.drop_table("case_evidence_links")
    op.drop_table("payment_cases")
    op.drop_table("evidence_relationships")
    op.drop_table("evidence_records")
