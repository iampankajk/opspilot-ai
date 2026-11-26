"""Provider output, HTTP contracts, and saved views remain separate from ORM models."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import core_schema

from app.evidence_schemas import EvidenceRecordView, EvidenceRelationshipView, SourceOutcome
from app.workspace_schemas import LocalID, Schema, ThreadKind

QuerySource = Literal["internal_payments", "stripe", "loki", "tempo", "zendesk", "support_lookup"]
ProposalStatus = Literal["confirmed", "not_confirmed", "inconclusive"]
GenerationStatus = Literal["pending", "completed", "failed", "interrupted", "stale"]
ProviderName = Literal["mock", "openai", "gemini"]


def storable_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text contains a null character")
    return value


ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
    AfterValidator(storable_text),
]
StatementText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=400),
    AfterValidator(storable_text),
]
CitationIndex = Annotated[int, Field(ge=0, lt=8)]


def system_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("System timestamps require a timezone")
    return value.astimezone(UTC)


SystemTime = Annotated[datetime, AfterValidator(system_time)]


class OutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CitationDraft(OutputSchema):
    evidence_record_id: LocalID
    pointer: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    role: Literal["supports", "contradicts", "context"]
    explanation: ShortText


class BasisStatement(OutputSchema):
    text: StatementText
    kind: Literal["evidence_statement", "unverified_hypothesis"]
    citation_indexes: list[CitationIndex] = Field(max_length=8)
    result_source_keys: list[QuerySource] = Field(max_length=6)

    @model_validator(mode="after")
    def unique_basis(self):
        if len(set(self.citation_indexes)) != len(self.citation_indexes) or len(
            set(self.result_source_keys)
        ) != len(self.result_source_keys):
            raise ValueError("Duplicate basis reference")
        if self.kind == "evidence_statement" and not (
            self.citation_indexes or self.result_source_keys
        ):
            raise ValueError("Evidence statement requires a basis")
        return self


class FindingDraft(OutputSchema):
    kind: Literal["observation", "hypothesis"]
    claim: ShortText
    proposed_status: ProposalStatus
    citations: list[CitationDraft] = Field(max_length=8)
    rationale: list[BasisStatement] = Field(min_length=1, max_length=3)
    limitations: list[BasisStatement] = Field(max_length=4)
    next_questions: list[ShortText] = Field(max_length=3)


class FindingGenerationOutput(OutputSchema):
    schema_version: Literal["task5.v1"]
    findings: list[FindingDraft] = Field(max_length=6)
    no_findings_reason: Literal["no_assessable_claims"] | None

    @model_validator(mode="after")
    def empty_reason(self):
        if (not self.findings) != (self.no_findings_reason is not None):
            raise ValueError("Empty findings require exactly one reason")
        return self


class FindingsProviderJsonSchema(GenerateJsonSchema):
    def str_schema(self, schema: core_schema.StringSchema):
        result = super().str_schema(schema)
        # Keep length constraints in Pydantic, independent of OpenAI's schema subset.
        result.pop("minLength", None)
        result.pop("maxLength", None)
        return result


class FindingGenerationCreate(Schema):
    state_id: UUID
    expected_draft_version: int = Field(ge=0, strict=True)
    evidence_request_id: UUID
    retry_of_generation_id: UUID | None = None


class FindingsQuery(Schema):
    state_id: UUID


class GroundedRecord(EvidenceRecordView):
    field_provenance: dict


class GroundedOutcome(SourceOutcome):
    records: list[GroundedRecord]

    @model_validator(mode="after")
    def terminal_outcome(self):
        if self.execution_status == "completed" and (
            (self.availability == "included") == (self.match_status == "not_evaluated")
        ):
            raise ValueError(
                "Included completion must be evaluated; declared gaps stay unevaluated"
            )
        if self.availability != "included" and self.records:
            raise ValueError("Unavailable sources cannot supply records")
        return self


class StoredBasis(Schema):
    text: str
    kind: Literal["evidence_statement", "unverified_hypothesis"]
    citation_ids: list[UUID]
    result_ref_ids: list[UUID]


class StoredCitation(CitationDraft):
    # OutputSchema's strict UUID handling is unsuitable for HTTP restoration from JSON.
    citation_id: UUID
    source_key: QuerySource
    value: object


class StoredResultRef(Schema):
    result_ref_id: UUID
    request_id: UUID
    source_key: QuerySource
    explanation: str


class StoredFinding(Schema):
    finding_id: UUID
    generation_id: UUID
    logical_finding_ref: str
    claim: str
    kind: Literal["observation", "hypothesis"]
    related_case_id: LocalID
    current_proposal_id: UUID
    proposed_status: ProposalStatus
    rationale: list[StoredBasis]
    limitations: list[StoredBasis]
    next_questions: list[str]
    citations: list[StoredCitation]
    result_refs: list[StoredResultRef]
    generated_at: SystemTime
    review_state: Literal["awaiting_review"] = "awaiting_review"


class GenerationHistory(Schema):
    generation_id: UUID
    evidence_request_id: UUID
    retry_of_generation_id: UUID | None
    status: GenerationStatus
    requested_at: SystemTime
    deadline_at: SystemTime
    finished_at: SystemTime | None
    failure_code: str | None
    retryable: bool
    provider: ProviderName
    configured_model: str
    returned_model: str | None
    prompt_version: str
    schema_version: str
    usage: dict | None
    estimated_cost_usd: Decimal | None
    actual_cost_usd: Decimal | None


class CaseFindings(Schema):
    request_id: UUID
    investigation_id: UUID
    state_id: UUID
    draft_version: int = Field(ge=0)
    thread_kind: ThreadKind
    case_id: LocalID
    generation_status: Literal[
        "not_started", "pending", "completed", "failed", "interrupted", "stale"
    ]
    latest_generation_id: UUID | None
    successful_generation_id: UUID | None
    no_findings_reason: Literal["no_assessable_claims"] | None
    findings: list[StoredFinding]
    cited_records: list[GroundedRecord]
    source_outcomes: list[GroundedOutcome]
    relationships: list[EvidenceRelationshipView]
    generation_history: list[GenerationHistory]
