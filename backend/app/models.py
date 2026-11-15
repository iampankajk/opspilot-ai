from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "ix": "ix_%(table_name)s_%(column_0_name)s",
        }
    )


class VisitorContext(Base):
    __tablename__ = "visitor_contexts"
    __table_args__ = (
        CheckConstraint("octet_length(session_token_hash) = 32", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint(
            "invalidated_at IS NULL OR invalidated_at >= created_at",
            name="invalidation_after_creation",
        ),
    )

    visitor_context_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session_token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        CheckConstraint("btrim(version_label) <> ''", name="version_label_nonblank"),
        CheckConstraint("fixture_digest ~ '^[0-9a-f]{64}$'", name="digest_sha256_hex"),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version_label: Mapped[str] = mapped_column(Text, unique=True)
    fixture_digest: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSONB)
    provenance: Mapped[dict] = mapped_column(JSONB)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("source_namespace", "source_incident_reference"),
        CheckConstraint("btrim(source_namespace) <> ''", name="source_namespace_nonblank"),
        CheckConstraint("btrim(source_incident_reference) <> ''", name="source_reference_nonblank"),
    )

    incident_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_namespace: Mapped[str] = mapped_column(Text)
    source_incident_reference: Mapped[str] = mapped_column(Text)


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (UniqueConstraint("visitor_context_id", "incident_id"),)

    investigation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    visitor_context_id: Mapped[UUID] = mapped_column(
        ForeignKey("visitor_contexts.visitor_context_id", ondelete="RESTRICT"), index=True
    )
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.incident_id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationState(Base):
    __tablename__ = "investigation_states"
    __table_args__ = (UniqueConstraint("state_id", "investigation_id"),)

    state_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.investigation_id", ondelete="RESTRICT"), index=True
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    incident_context: Mapped[dict] = mapped_column(JSONB)
    limitations: Mapped[list] = mapped_column(JSONB)


class WorkingDraft(Base):
    __tablename__ = "working_drafts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "investigation_id"],
            ["investigation_states.state_id", "investigation_states.investigation_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("draft_version >= 0", name="nonnegative_version"),
    )

    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.investigation_id", ondelete="RESTRICT"), primary_key=True
    )
    state_id: Mapped[UUID] = mapped_column(unique=True)
    draft_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    has_unversioned_changes: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    persisted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ThreadState(Base):
    __tablename__ = "thread_states"
    __table_args__ = (
        CheckConstraint(
            "thread_kind IN ('payment_failures', 'possible_duplicates')", name="thread_kind"
        ),
    )

    state_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigation_states.state_id", ondelete="RESTRICT"), primary_key=True
    )
    thread_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    summary: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[list] = mapped_column(JSONB)
    unresolved_questions: Mapped[list] = mapped_column(JSONB)
    presentation: Mapped[dict] = mapped_column(JSONB)


class StateSource(Base):
    __tablename__ = "state_sources"
    __table_args__ = (
        CheckConstraint(
            "availability IN ('included', 'not_included', 'not_constructed', 'unavailable')",
            name="availability",
        ),
        CheckConstraint(
            "completeness IN ('unverified', 'known_partial', "
            "'verified_for_stated_scope', 'not_applicable')",
            name="completeness",
        ),
    )

    state_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigation_states.state_id", ondelete="RESTRICT"), primary_key=True
    )
    source_key: Mapped[str] = mapped_column(Text, primary_key=True)
    source_name: Mapped[str] = mapped_column(Text)
    source_category: Mapped[str] = mapped_column(Text)
    availability: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    completeness: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list] = mapped_column(JSONB)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "source_key"],
            ["state_sources.state_id", "state_sources.source_key"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "evidence_record_id", "source_key"),
        CheckConstraint("evidence_record_id ~ '^[A-Za-z0-9._:-]{1,128}$'", name="local_id"),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_key: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(Text)
    record_type: Mapped[str] = mapped_column(Text)
    source_record_reference: Mapped[str | None] = mapped_column(Text)
    fixture_provenance: Mapped[dict] = mapped_column(JSONB)
    source_digest: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    raw_markdown: Mapped[str] = mapped_column(Text)
    timestamps: Mapped[list] = mapped_column(JSONB)
    field_provenance: Mapped[dict] = mapped_column(JSONB)


class PaymentCase(Base):
    __tablename__ = "payment_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "primary_report_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "case_reference"),
        CheckConstraint("case_id ~ '^[A-Za-z0-9._:-]{1,128}$'", name="local_id"),
        CheckConstraint(
            "(reported_amount IS NULL) = (reported_currency IS NULL)", name="money_pair"
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_reference: Mapped[str] = mapped_column(Text)
    primary_report_record_id: Mapped[str] = mapped_column(Text)
    customer_ref: Mapped[str | None] = mapped_column(Text)
    reported_order_ref: Mapped[str | None] = mapped_column(Text)
    related_order_refs: Mapped[list] = mapped_column(JSONB)
    reported_issue: Mapped[str] = mapped_column(Text)
    reported_amount: Mapped[Decimal | None] = mapped_column(Numeric())
    reported_currency: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[dict] = mapped_column(JSONB)
    payment_state: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    field_provenance: Mapped[dict] = mapped_column(JSONB)


class CaseThread(Base):
    __tablename__ = "case_threads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "thread_kind"],
            ["thread_states.state_id", "thread_states.thread_kind"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "case_id"],
            ["payment_cases.state_id", "payment_cases.case_id"],
            ondelete="RESTRICT",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    thread_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, primary_key=True)


class CaseEvidenceLink(Base):
    __tablename__ = "case_evidence_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "case_id"],
            ["payment_cases.state_id", "payment_cases.case_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "evidence_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_case_evidence_links_record",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "basis_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_case_evidence_links_basis",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "category IN ('direct_ref_match', 'documented_lookup', "
            "'field_match', 'temporal_context', 'unverified')",
            name="category",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    evidence_record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text)
    matched_fields: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)
    basis_record_id: Mapped[str | None] = mapped_column(Text)


class EvidenceRelationship(Base):
    __tablename__ = "evidence_relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "from_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_from_record",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "to_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_to_record",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "basis_record_id"],
            ["evidence_records.state_id", "evidence_records.evidence_record_id"],
            name="fk_evidence_relationships_basis",
            ondelete="RESTRICT",
        ),
        CheckConstraint("relationship_id ~ '^[A-Za-z0-9._:-]{1,128}$'", name="local_id"),
        CheckConstraint(
            "category IN ('direct_ref_match', 'documented_lookup', "
            "'field_match', 'temporal_context', 'unverified')",
            name="category",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    relationship_id: Mapped[str] = mapped_column(Text, primary_key=True)
    from_record_id: Mapped[str] = mapped_column(Text)
    to_record_id: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    matched_fields: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)
    basis_record_id: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list] = mapped_column(JSONB)


class EvidenceRequest(Base):
    __tablename__ = "evidence_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "thread_kind"],
            ["thread_states.state_id", "thread_states.thread_kind"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "thread_kind", "case_id"],
            ["case_threads.state_id", "case_threads.thread_kind", "case_threads.case_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "retry_of_request_id"],
            ["evidence_requests.state_id", "evidence_requests.request_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending','completed','partial','failed','interrupted','stale')",
            name="status",
        ),
        CheckConstraint("deadline_at > requested_at", name="deadline"),
        CheckConstraint("expected_draft_version >= 0", name="version"),
        CheckConstraint(
            "(status = 'pending' AND finished_at IS NULL) OR "
            "(status <> 'pending' AND finished_at IS NOT NULL AND finished_at >= requested_at)",
            name="finished",
        ),
        CheckConstraint("retry_of_request_id <> request_id", name="not_self_retry"),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_kind: Mapped[str] = mapped_column(Text)
    case_id: Mapped[str | None] = mapped_column(Text)
    initiator: Mapped[str] = mapped_column(Text)
    query_kind: Mapped[str] = mapped_column(Text)
    criteria: Mapped[dict] = mapped_column(JSONB)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    expected_draft_version: Mapped[int] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(Text)
    retry_of_request_id: Mapped[UUID | None] = mapped_column()


class RequestSource(Base):
    __tablename__ = "request_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "request_id"],
            ["evidence_requests.state_id", "evidence_requests.request_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "source_key"],
            ["state_sources.state_id", "state_sources.source_key"],
            ondelete="RESTRICT",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(Text, primary_key=True)


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "request_id", "source_key"],
            [
                "request_sources.state_id",
                "request_sources.request_id",
                "request_sources.source_key",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "execution_status IN ('pending','completed','failed','interrupted')", name="execution"
        ),
        CheckConstraint(
            "availability IN ('included','not_included','not_constructed','unavailable')",
            name="availability",
        ),
        CheckConstraint("match_status IN ('matches','no_matches','not_evaluated')", name="match"),
        CheckConstraint(
            "completeness IN ('unverified','known_partial',"
            "'verified_for_stated_scope','not_applicable')",
            name="completeness",
        ),
        CheckConstraint(
            "(execution_status = 'completed' AND match_status = 'matches' "
            "AND returned_count IS NOT NULL AND returned_count > 0) OR "
            "(execution_status = 'completed' AND match_status = 'no_matches' "
            "AND returned_count IS NOT NULL AND returned_count = 0) OR "
            "(match_status = 'not_evaluated' AND returned_count IS NULL)",
            name="count",
        ),
        CheckConstraint(
            "(execution_status = 'pending' AND completed_at IS NULL) OR "
            "(execution_status <> 'pending' AND completed_at IS NOT NULL)",
            name="finished",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(Text, primary_key=True)
    execution_status: Mapped[str] = mapped_column(Text)
    availability: Mapped[str] = mapped_column(Text)
    match_status: Mapped[str] = mapped_column(Text)
    returned_count: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str | None] = mapped_column(Text)
    completeness: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(Text)


class RetrievalResultRecord(Base):
    __tablename__ = "retrieval_result_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "request_id", "source_key"],
            [
                "retrieval_results.state_id",
                "retrieval_results.request_id",
                "retrieval_results.source_key",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "evidence_record_id", "source_key"],
            [
                "evidence_records.state_id",
                "evidence_records.evidence_record_id",
                "evidence_records.source_key",
            ],
            ondelete="RESTRICT",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(Text, primary_key=True)
    evidence_record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    match_basis: Mapped[dict] = mapped_column(JSONB)


class AIGenerationRequest(Base):
    __tablename__ = "ai_generation_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "thread_kind", "case_id"],
            ["case_threads.state_id", "case_threads.thread_kind", "case_threads.case_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "evidence_request_id"],
            ["evidence_requests.state_id", "evidence_requests.request_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "retry_of_generation_id"],
            ["ai_generation_requests.state_id", "ai_generation_requests.generation_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "generation_id", "thread_kind", name="uq_generation_thread"),
        UniqueConstraint(
            "state_id", "generation_id", "evidence_request_id", name="uq_generation_request"
        ),
        CheckConstraint(
            "status IN ('pending','completed','failed','interrupted','stale')", name="status"
        ),
        CheckConstraint("deadline_at > requested_at", name="deadline"),
        CheckConstraint(
            "expected_draft_version >= 0 AND post_start_version = expected_draft_version + 1",
            name="versions",
        ),
        CheckConstraint("retry_of_generation_id <> generation_id", name="not_self_retry"),
        CheckConstraint(
            "(status = 'pending' AND finished_at IS NULL) OR (status <> 'pending' AND "
            "finished_at IS NOT NULL AND finished_at >= requested_at)",
            name="finished",
        ),
        CheckConstraint(
            "(status = 'completed' AND normalized_output IS NOT NULL) OR "
            "(status <> 'completed' AND normalized_output IS NULL)",
            name="output",
        ),
        CheckConstraint("reserved_cost_usd IS NULL OR reserved_cost_usd >= 0", name="reserve"),
        CheckConstraint("actual_cost_usd IS NULL OR actual_cost_usd >= 0", name="cost"),
        Index(
            "uq_ai_generation_completed_scope",
            "state_id",
            "thread_kind",
            "case_id",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_kind: Mapped[str] = mapped_column(Text)
    case_id: Mapped[str] = mapped_column(Text)
    evidence_request_id: Mapped[UUID] = mapped_column()
    retry_of_generation_id: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_draft_version: Mapped[int] = mapped_column(Integer)
    post_start_version: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    configured_model: Mapped[str] = mapped_column(Text)
    returned_model: Mapped[str | None] = mapped_column(Text)
    provider_response_id: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(Text)
    input_bundle: Mapped[dict] = mapped_column(JSONB)
    input_digest: Mapped[str] = mapped_column(String(64))
    budget: Mapped[dict] = mapped_column(JSONB)
    counted_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reserved_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric())
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric())
    usage: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    normalized_output: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "thread_kind"],
            ["thread_states.state_id", "thread_states.thread_kind"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "generation_id", "thread_kind"],
            [
                "ai_generation_requests.state_id",
                "ai_generation_requests.generation_id",
                "ai_generation_requests.thread_kind",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "finding_id", "current_proposal_id"],
            ["ai_proposals.state_id", "ai_proposals.finding_id", "ai_proposals.proposal_id"],
            name="fk_findings_current_proposal",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "finding_id", "thread_kind", name="uq_finding_thread"),
        UniqueConstraint("state_id", "finding_id", "generation_id", name="uq_finding_generation"),
        UniqueConstraint(
            "state_id", "thread_kind", "logical_finding_ref", name="uq_finding_logical"
        ),
        CheckConstraint("kind IN ('observation','hypothesis')", name="kind"),
        CheckConstraint("btrim(claim) <> '' AND length(claim) <= 240", name="claim"),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column()
    thread_kind: Mapped[str] = mapped_column(Text)
    logical_finding_ref: Mapped[str] = mapped_column(Text)
    claim: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_proposal_id: Mapped[UUID | None] = mapped_column()


class FindingCase(Base):
    __tablename__ = "finding_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "finding_id", "thread_kind"],
            ["findings.state_id", "findings.finding_id", "findings.thread_kind"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "thread_kind", "case_id"],
            ["case_threads.state_id", "case_threads.thread_kind", "case_threads.case_id"],
            ondelete="RESTRICT",
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_kind: Mapped[str] = mapped_column(Text)


class AIProposal(Base):
    __tablename__ = "ai_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "finding_id", "generation_id"],
            ["findings.state_id", "findings.finding_id", "findings.generation_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "generation_id", "evidence_request_id"],
            [
                "ai_generation_requests.state_id",
                "ai_generation_requests.generation_id",
                "ai_generation_requests.evidence_request_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "finding_id", "proposal_id", name="uq_proposal_finding"),
        UniqueConstraint(
            "state_id", "proposal_id", "evidence_request_id", name="uq_proposal_request"
        ),
        CheckConstraint(
            "proposed_status IN ('confirmed','not_confirmed','inconclusive')", name="status"
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    proposal_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column()
    generation_id: Mapped[UUID] = mapped_column()
    evidence_request_id: Mapped[UUID] = mapped_column()
    proposed_status: Mapped[str] = mapped_column(Text)
    rationale: Mapped[list] = mapped_column(JSONB)
    limitations: Mapped[list] = mapped_column(JSONB)
    next_questions: Mapped[list] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceCitation(Base):
    __tablename__ = "evidence_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "proposal_id", "request_id"],
            [
                "ai_proposals.state_id",
                "ai_proposals.proposal_id",
                "ai_proposals.evidence_request_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "request_id", "source_key", "evidence_record_id"],
            [
                "retrieval_result_records.state_id",
                "retrieval_result_records.request_id",
                "retrieval_result_records.source_key",
                "retrieval_result_records.evidence_record_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("state_id", "proposal_id", "ordinal"),
        CheckConstraint("ordinal >= 0 AND ordinal < 8", name="ordinal"),
        CheckConstraint("role IN ('supports','contradicts','context')", name="role"),
        CheckConstraint("length(pointer) BETWEEN 1 AND 256", name="pointer"),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    citation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column()
    request_id: Mapped[UUID] = mapped_column()
    source_key: Mapped[str] = mapped_column(Text)
    evidence_record_id: Mapped[str] = mapped_column(Text)
    pointer: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)


class AssessmentResultRef(Base):
    __tablename__ = "assessment_result_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "proposal_id", "request_id"],
            [
                "ai_proposals.state_id",
                "ai_proposals.proposal_id",
                "ai_proposals.evidence_request_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["state_id", "request_id", "source_key"],
            [
                "retrieval_results.state_id",
                "retrieval_results.request_id",
                "retrieval_results.source_key",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("statement_kind IN ('rationale','limitations')", name="statement_kind"),
        CheckConstraint("statement_index >= 0", name="statement_index"),
        UniqueConstraint(
            "state_id", "proposal_id", "statement_kind", "statement_index", "source_key"
        ),
    )
    state_id: Mapped[UUID] = mapped_column(primary_key=True)
    result_ref_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column()
    request_id: Mapped[UUID] = mapped_column()
    source_key: Mapped[str] = mapped_column(Text)
    statement_kind: Mapped[str] = mapped_column(Text)
    statement_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
