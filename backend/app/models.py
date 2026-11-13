from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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
