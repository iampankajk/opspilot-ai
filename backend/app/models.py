from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
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
