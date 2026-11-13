from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ThreadKind = Literal["payment_failures", "possible_duplicates"]
SourceKey = Literal[
    "incident_alert",
    "metrics",
    "deployment_history",
    "internal_payments",
    "stripe",
    "zendesk",
    "support_lookup",
    "loki",
    "tempo",
]
LocalID = Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,128}$")]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceTime(Schema):
    role: str
    raw: str | None
    timezone: str | None
    precision: Literal["second", "minute", "minute_range", "unknown", "not_applicable"]
    utc_lower: datetime | None
    utc_upper: datetime | None
    missing_reason: str | None

    @field_validator("utc_lower", "utc_upper")
    @classmethod
    def utc_time(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Normalized source bounds require a timezone")
            return value.astimezone(UTC)
        return value


class DatasetVersionResponse(Schema):
    dataset_version_id: UUID
    version_label: str
    fixture_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class IncidentContext(Schema):
    incident_id: UUID
    incident_ref: LocalID
    title: str
    description: str | None
    category: str | None
    severity: str | None
    region: str | None
    synthetic: Literal[True]
    incident_time: SourceTime
    source_alert_record_id: LocalID


class IncidentEntry(Schema):
    incident: IncidentContext
    dataset_version: DatasetVersionResponse


class InvestigationCreate(Schema):
    incident_id: UUID


class WorkspaceThread(Schema):
    thread_kind: ThreadKind
    label: str
    case_count: int = Field(ge=0)


class Workspace(Schema):
    investigation_id: UUID
    state_id: UUID
    draft_version: int = Field(ge=0)
    dataset_version: DatasetVersionResponse
    incident: IncidentContext
    threads: list[WorkspaceThread] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def exactly_two_kinds(self):
        if {thread.thread_kind for thread in self.threads} != {
            "payment_failures",
            "possible_duplicates",
        }:
            raise ValueError("Exactly one of each approved thread is required")
        return self


class Money(Schema):
    amount: str = Field(pattern=r"^-?\d+(\.\d+)?$")
    currency: str


class RelatedOrderReference(Schema):
    value: str
    association: Literal["direct", "candidate", "contextual"]
    basis_record_id: LocalID


class PaymentState(Schema):
    label: str
    basis_record_ids: list[LocalID]
    limitations: list[str]


class AssociationBasis(Schema):
    category: Literal[
        "direct_ref_match", "documented_lookup", "field_match", "temporal_context", "unverified"
    ]
    matched_fields: dict
    explanation: str
    basis_record_id: LocalID | None


class CaseSummary(Schema):
    case_id: LocalID
    case_reference: str
    primary_report_record_id: LocalID
    customer_ref: str | None
    reported_order_ref: str | None
    related_order_refs: list[RelatedOrderReference]
    reported_issue: str
    reported_money: Money | None
    reported_at: SourceTime
    payment_state: PaymentState | None
    investigation_progress: Literal["not_started"] = "not_started"


class CaseList(Schema):
    investigation_id: UUID
    state_id: UUID
    draft_version: int = Field(ge=0)
    thread_kind: ThreadKind
    cases: list[CaseSummary]


class CaseListQuery(Schema):
    state_id: UUID
