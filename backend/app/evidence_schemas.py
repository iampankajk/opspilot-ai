from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.workspace_schemas import (
    AssociationBasis,
    LocalID,
    Schema,
    SourceKey,
    SourceTime,
    ThreadKind,
)

QUERY_SOURCES = ("internal_payments", "stripe", "loki", "tempo", "zendesk", "support_lookup")
GROUPS = {
    "internal_payments": ("internal_payments",),
    "provider": ("stripe",),
    "logs_traces": ("loki", "tempo"),
    "support_tickets": ("zendesk", "support_lookup"),
}


class EvidenceRequestCreate(Schema):
    state_id: UUID
    expected_draft_version: int = Field(ge=0, strict=True)
    retry_of_request_id: UUID | None = None


class RetrievalCriteria(Schema):
    """Server-built allowlist, never a caller-supplied query language."""

    state_id: UUID
    thread_kind: ThreadKind
    case_id: LocalID
    source_keys: tuple[SourceKey, ...]
    record_ids: list[LocalID] = Field(max_length=14)
    max_records: int = Field(ge=0, le=14)

    @model_validator(mode="after")
    def bounded(self):
        if (
            self.source_keys != QUERY_SOURCES
            or len(set(self.record_ids)) != len(self.record_ids)
            or self.max_records != len(self.record_ids)
        ):
            raise ValueError("Criteria must contain the complete approved case inventory")
        return self


class FixtureProvenance(Schema):
    version_label: str = Field(min_length=1)
    fixture_record_id: LocalID
    origin: str = Field(min_length=1)


class EvidenceRecordView(Schema):
    evidence_record_id: LocalID
    source_key: SourceKey
    source_name: str
    record_type: str
    source_record_reference: str | None
    synthetic: Literal[True] = True
    fixture_provenance: FixtureProvenance
    timestamps: list[SourceTime]
    payload: dict
    case_association: AssociationBasis


class EvidenceRelationshipView(Schema):
    relationship_id: LocalID
    from_record_id: LocalID
    to_record_id: LocalID
    basis: AssociationBasis
    attribution: str
    limitations: list[str]


class SourceOutcome(Schema):
    source_key: SourceKey
    source_name: str
    execution_status: Literal["completed", "failed", "interrupted"]
    availability: Literal["included", "not_included", "not_constructed", "unavailable"]
    match_status: Literal["matches", "no_matches", "not_evaluated"]
    returned_count: int | None = Field(ge=0)
    records: list[EvidenceRecordView]
    scope: str | None
    completeness: Literal[
        "unverified", "known_partial", "verified_for_stated_scope", "not_applicable"
    ]
    limitations: list[str]
    error_code: str | None

    @model_validator(mode="after")
    def count_matches_membership(self):
        evaluated = self.execution_status == "completed" and self.match_status != "not_evaluated"
        if evaluated:
            if self.returned_count != len(self.records) or self.match_status != (
                "matches" if self.records else "no_matches"
            ):
                raise ValueError("Incomplete source result")
        elif self.returned_count is not None or self.records:
            raise ValueError("Unevaluated sources cannot return records or counts")
        if any(record.source_key != self.source_key for record in self.records):
            raise ValueError("Source mismatch")
        return self


class EvidenceGroup(Schema):
    group_kind: Literal["internal_payments", "provider", "logs_traces", "support_tickets"]
    sources: list[SourceOutcome]


class CaseEvidence(Schema):
    request_id: UUID
    evidence_request_id: UUID
    investigation_id: UUID
    state_id: UUID
    draft_version: int = Field(ge=0)
    thread_kind: ThreadKind
    case_id: LocalID
    status: Literal["completed", "partial"]
    groups: list[EvidenceGroup]
    relationships: list[EvidenceRelationshipView]
