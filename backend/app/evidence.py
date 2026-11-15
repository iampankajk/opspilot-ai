"""Bounded, synchronous evidence inspection with durable start/outcome transactions."""

from datetime import timedelta
from time import monotonic
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.catalog import canonical_digest
from app.evidence_schemas import (
    GROUPS,
    QUERY_SOURCES,
    CaseEvidence,
    EvidenceGroup,
    EvidenceRecordView,
    EvidenceRelationshipView,
    EvidenceRequestCreate,
    RetrievalCriteria,
    SourceOutcome,
)
from app.models import (
    CaseEvidenceLink,
    CaseThread,
    DatasetVersion,
    EvidenceRecord,
    EvidenceRelationship,
    EvidenceRequest,
    Investigation,
    InvestigationState,
    RequestSource,
    RetrievalResult,
    RetrievalResultRecord,
    StateSource,
    WorkingDraft,
)
from app.visitor_sessions import COOKIE_NAME, Clock, CurrentVisitor, authenticate, get_clock
from app.workspace_schemas import AssociationBasis, LocalID, ThreadKind

router = APIRouter(prefix="/api/v1")
DEADLINE_SECONDS = 10
# Engine pool checkout + physical connection each have a three-second upper bound.
CONNECTION_RESERVE = 6


def failure(code="EVIDENCE_RETRIEVAL_FAILED", **details):
    return APIError(
        503,
        code,
        "Evidence could not be retrieved. Reload the workspace and retry.",
        details=details,
    )


def conflict(code, draft):
    return APIError(
        409,
        code,
        "Reload the workspace before retrying evidence inspection.",
        details={"state_id": str(draft.state_id), "draft_version": draft.draft_version},
    )


def owned_draft(db, request, investigation_id, clock, state_id=None):
    actor = authenticate(db, request.cookies.get(COOKIE_NAME), clock)
    investigation = db.scalar(
        select(Investigation)
        .where(
            Investigation.investigation_id == investigation_id,
            Investigation.visitor_context_id == actor.visitor_context_id,
        )
        .with_for_update()
    )
    if investigation is None:
        raise APIError(404, "NOT_FOUND", "Resource not found.")
    draft = db.get(WorkingDraft, investigation_id)
    if draft is None:
        raise failure()
    if state_id is not None and draft.state_id != state_id:
        raise conflict("STALE_STATE", draft)
    return draft


def check_case(db, draft, thread, case):
    if db.get(CaseThread, (draft.state_id, thread, case)) is None:
        raise APIError(404, "NOT_FOUND", "Resource not found.")


def advance(draft, clock):
    draft.draft_version += 1
    draft.persisted_at = clock()
    draft.has_unversioned_changes = True


def interrupt(db, operation, clock, status="interrupted", code="REQUEST_INTERRUPTED"):
    operation.status, operation.failure_code = status, code
    operation.finished_at = max(clock(), operation.requested_at)
    for result in db.scalars(
        select(RetrievalResult).where(
            RetrievalResult.state_id == operation.state_id,
            RetrievalResult.request_id == operation.request_id,
            RetrievalResult.execution_status == "pending",
        )
    ):
        result.execution_status, result.match_status = "interrupted", "not_evaluated"
        result.returned_count, result.error_code = None, code
        result.completed_at = operation.finished_at


def reconcile_overdue(db, draft, clock):
    """Called only with the owned investigation locked and its current draft selected."""
    overdue = db.scalars(
        select(EvidenceRequest).where(
            EvidenceRequest.state_id == draft.state_id,
            EvidenceRequest.status == "pending",
            EvidenceRequest.deadline_at <= clock(),
        )
    ).all()
    for operation in overdue:
        interrupt(db, operation, clock)
    if overdue:
        advance(draft, clock)
    return bool(overdue)


def reconcile_owned(request, investigation_id, state_id, thread, case, clock):
    # Independent commit: a subsequent stale-version rejection cannot undo recovery.
    with Session(request.app.state.engine) as db, db.begin():
        draft = owned_draft(db, request, investigation_id, clock, state_id)
        check_case(db, draft, thread, case)
        reconcile_overdue(db, draft, clock)
        authenticate(db, request.cookies.get(COOKIE_NAME), clock)


def start(request, investigation_id, thread, case, payload, clock):
    reconcile_owned(request, investigation_id, payload.state_id, thread, case, clock)
    with Session(request.app.state.engine) as db, db.begin():
        draft = owned_draft(db, request, investigation_id, clock, payload.state_id)
        check_case(db, draft, thread, case)
        if draft.draft_version != payload.expected_draft_version:
            raise conflict("STALE_DRAFT_VERSION", draft)
        if db.scalar(
            select(EvidenceRequest.request_id)
            .where(
                EvidenceRequest.state_id == draft.state_id,
                EvidenceRequest.status == "pending",
            )
            .limit(1)
        ):
            raise conflict("OPERATION_IN_PROGRESS", draft)
        if payload.retry_of_request_id is not None:
            prior = db.get(EvidenceRequest, (draft.state_id, payload.retry_of_request_id))
            if (
                prior is None
                or prior.thread_kind != thread
                or prior.case_id != case
                or prior.status not in {"partial", "failed", "interrupted"}
            ):
                raise conflict("INVALID_RETRY_REFERENCE", draft)
        state = db.get(InvestigationState, draft.state_id)
        dataset = db.get(DatasetVersion, state.dataset_version_id)
        case_map = next((c for c in dataset.manifest["cases"] if c["case_id"] == case), None)
        if case_map is None or thread not in case_map["thread_kinds"]:
            raise failure()
        criteria = RetrievalCriteria(
            state_id=draft.state_id,
            thread_kind=thread,
            case_id=case,
            source_keys=QUERY_SOURCES,
            record_ids=case_map["evidence_record_ids"],
            max_records=len(case_map["evidence_record_ids"]),
        )
        inventory = {r["record_id"]: r for r in dataset.manifest["records"]}
        if any(
            inventory.get(i, {}).get("source_key") not in QUERY_SOURCES for i in criteria.record_ids
        ):
            raise failure()
        sources = {}
        for key in QUERY_SOURCES:
            source = db.get(StateSource, (draft.state_id, key))
            if source is None:
                raise failure()
            sources[key] = {
                field: getattr(source, field)
                for field in (
                    "source_key",
                    "source_name",
                    "availability",
                    "scope",
                    "completeness",
                    "limitations",
                )
            }
        now, request_id = clock(), uuid4()
        end = monotonic() + DEADLINE_SECONDS
        db.add(
            EvidenceRequest(
                state_id=draft.state_id,
                request_id=request_id,
                thread_kind=thread,
                case_id=case,
                initiator="investigator",
                query_kind="case_evidence",
                criteria=criteria.model_dump(mode="json"),
                requested_at=now,
                deadline_at=now + timedelta(seconds=DEADLINE_SECONDS),
                status="pending",
                expected_draft_version=payload.expected_draft_version,
                retry_of_request_id=payload.retry_of_request_id,
            )
        )
        db.flush()
        for key in QUERY_SOURCES:
            db.add(RequestSource(state_id=draft.state_id, request_id=request_id, source_key=key))
        db.flush()
        for key, source in sources.items():
            db.add(
                RetrievalResult(
                    state_id=draft.state_id,
                    request_id=request_id,
                    source_key=key,
                    execution_status="pending",
                    availability=source["availability"],
                    match_status="not_evaluated",
                    returned_count=None,
                    completed_at=None,
                    scope=source["scope"],
                    completeness=source["completeness"],
                    limitations=source["limitations"],
                    error_code=None,
                )
            )
        advance(draft, clock)
        db.flush()
        authenticate(db, request.cookies.get(COOKIE_NAME), clock)
        return request_id, draft.draft_version, criteria, sources, inventory, end


def basis(row):
    return AssociationBasis(
        **{
            key: getattr(row, key)
            for key in ("category", "matched_fields", "explanation", "basis_record_id")
        }
    )


def record_chronology(record: EvidenceRecordView):
    # SourceTime normalizes known offsets to UTC. Use only declared usable source times;
    # range starts are ordering bounds, not invented exact event times.
    times = [
        time.utc_lower
        for time in record.timestamps
        if time.utc_lower is not None
        and time.timezone
        and time.precision in {"second", "minute", "minute_range"}
    ]
    earliest = min(times, default=None)
    # Unknown times follow timed records; equal bounds use a deterministic ID tie-break.
    return earliest is None, earliest, record.evidence_record_id


def read_source(request, criteria, key, inventory, end):
    remaining = end - monotonic()
    if remaining <= CONNECTION_RESERVE:
        raise TimeoutError()
    with Session(request.app.state.engine) as db, db.begin():
        # Reserve connection setup before acquiring it; re-evaluate after checkout.
        db.connection()
        remaining = end - monotonic()
        if remaining <= 0:
            raise TimeoutError()
        milliseconds = str(max(1, min(3000, int(remaining * 1000))))
        db.execute(
            text(
                "SELECT set_config('statement_timeout', :budget, true), "
                "set_config('lock_timeout', :budget, true)"
            ),
            {"budget": milliseconds},
        )
        rows = db.execute(
            select(EvidenceRecord, CaseEvidenceLink)
            .join(
                CaseEvidenceLink,
                (CaseEvidenceLink.state_id == EvidenceRecord.state_id)
                & (CaseEvidenceLink.evidence_record_id == EvidenceRecord.evidence_record_id),
            )
            .where(
                EvidenceRecord.state_id == criteria.state_id,
                EvidenceRecord.source_key == key,
                CaseEvidenceLink.case_id == criteria.case_id,
            )
            .order_by(EvidenceRecord.evidence_record_id)
            .limit(criteria.max_records + 1)
        ).all()
        expected = {i for i in criteria.record_ids if inventory[i]["source_key"] == key}
        if {row.evidence_record_id for row, _ in rows} != expected or len(rows) != len(expected):
            raise ValueError("Incomplete case source inventory")
        if any(
            canonical_digest(row.payload) != inventory[row.evidence_record_id]["payload_digest"]
            or row.source_digest != inventory[row.evidence_record_id]["payload_digest"]
            for row, _ in rows
        ):
            raise ValueError("Source payload does not match its pinned manifest")
        records = [
            EvidenceRecordView(
                evidence_record_id=row.evidence_record_id,
                source_key=row.source_key,
                source_name=row.source_name,
                record_type=row.record_type,
                source_record_reference=row.source_record_reference,
                fixture_provenance=row.fixture_provenance,
                timestamps=row.timestamps,
                payload=row.payload,
                case_association=basis(link),
            )
            for row, link in rows
        ]
        if monotonic() >= end:
            raise TimeoutError()
        return sorted(records, key=record_chronology)


def collect(request, criteria, sources, inventory, end):
    outcomes = {}
    for key in QUERY_SOURCES:
        values = sources[key]
        records, status, error, match, count = [], "completed", None, "not_evaluated", None
        if monotonic() >= end:
            status, error = "interrupted", "RETRIEVAL_DEADLINE"
        elif values["availability"] == "included":
            try:
                records = read_source(request, criteria, key, inventory, end)
                match, count = ("matches" if records else "no_matches"), len(records)
            except TimeoutError:
                status, error = "interrupted", "RETRIEVAL_DEADLINE"
            except (SQLAlchemyError, ValueError, RuntimeError):
                # Each source uses its own transaction; an aborted query cannot poison the next.
                status, error = "failed", "SOURCE_RETRIEVAL_FAILED"
        outcomes[key] = SourceOutcome(
            **values,
            execution_status=status,
            error_code=error,
            match_status=match,
            returned_count=count,
            records=records,
        )
    return outcomes


def persist_outcomes(db, operation, outcomes, clock):
    for key, outcome in outcomes.items():
        row = db.get(RetrievalResult, (operation.state_id, operation.request_id, key))
        for field in (
            "execution_status",
            "availability",
            "match_status",
            "returned_count",
            "scope",
            "completeness",
            "limitations",
            "error_code",
        ):
            setattr(row, field, getattr(outcome, field))
        row.completed_at = max(clock(), operation.requested_at)
    db.flush()
    for key, outcome in outcomes.items():
        for record in outcome.records:
            db.add(
                RetrievalResultRecord(
                    state_id=operation.state_id,
                    request_id=operation.request_id,
                    source_key=key,
                    evidence_record_id=record.evidence_record_id,
                    match_basis=record.case_association.model_dump(mode="json"),
                )
            )
    db.flush()
    counts = dict(
        db.execute(
            select(RetrievalResultRecord.source_key, func.count())
            .where(
                RetrievalResultRecord.state_id == operation.state_id,
                RetrievalResultRecord.request_id == operation.request_id,
            )
            .group_by(RetrievalResultRecord.source_key)
        ).all()
    )
    for key, outcome in outcomes.items():
        if counts.get(key, 0) != len(outcome.records):
            raise failure()


def finalize(
    request, investigation_id, thread, case, state_id, request_id, version, outcomes, clock
):
    rejected = None
    response = None
    with Session(request.app.state.engine) as db, db.begin():
        draft = owned_draft(db, request, investigation_id, clock)
        # A replaced state is never mutated, even to mark old work stale.
        if draft.state_id != state_id:
            raise conflict("STALE_STATE", draft)
        check_case(db, draft, thread, case)
        operation = db.get(EvidenceRequest, (state_id, request_id))
        if operation.status != "pending" or draft.draft_version != version:
            if operation.status == "pending":
                interrupt(db, operation, clock, "stale", "STALE_DRAFT_VERSION")
                advance(draft, clock)
            rejected = conflict("STALE_DRAFT_VERSION", draft)
        else:
            if clock() >= operation.deadline_at:
                # Even a late successful read cannot be published as completed.
                for key, old in outcomes.items():
                    outcomes[key] = old.model_copy(
                        update=dict(
                            execution_status="interrupted",
                            match_status="not_evaluated",
                            returned_count=None,
                            records=[],
                            error_code="RETRIEVAL_DEADLINE",
                        )
                    )
            completed = sum(o.execution_status == "completed" for o in outcomes.values())
            status = "completed" if completed == len(QUERY_SOURCES) else "partial"
            operation.status = (
                status
                if completed
                else (
                    "interrupted"
                    if all(o.execution_status == "interrupted" for o in outcomes.values())
                    else "failed"
                )
            )
            operation.finished_at = max(clock(), operation.requested_at)
            operation.failure_code = None if completed else "EVIDENCE_RETRIEVAL_FAILED"
            persist_outcomes(db, operation, outcomes, clock)
            advance(draft, clock)
            if not completed:
                rejected = failure(
                    evidence_request_id=str(request_id),
                    state_id=str(state_id),
                    draft_version=draft.draft_version,
                )
            else:
                ids = {r.evidence_record_id for o in outcomes.values() for r in o.records}
                # Only same-case returned endpoints and basis records can form displayed links.
                links = db.scalars(
                    select(EvidenceRelationship)
                    .where(
                        EvidenceRelationship.state_id == state_id,
                        EvidenceRelationship.from_record_id.in_(ids),
                        EvidenceRelationship.to_record_id.in_(ids),
                    )
                    .order_by(EvidenceRelationship.relationship_id)
                    .limit(15)
                ).all()
                relationships = [
                    EvidenceRelationshipView(
                        relationship_id=row.relationship_id,
                        from_record_id=row.from_record_id,
                        to_record_id=row.to_record_id,
                        basis=basis(row),
                        attribution=row.attribution,
                        limitations=row.limitations,
                    )
                    for row in links
                    if row.basis_record_id is None or row.basis_record_id in ids
                ]
                if len(links) > 14:
                    raise failure()
                response = CaseEvidence(
                    request_id=request.state.request_id,
                    evidence_request_id=request_id,
                    investigation_id=investigation_id,
                    state_id=state_id,
                    draft_version=draft.draft_version,
                    thread_kind=thread,
                    case_id=case,
                    status=status,
                    groups=[
                        EvidenceGroup(group_kind=group, sources=[outcomes[k] for k in keys])
                        for group, keys in GROUPS.items()
                    ],
                    relationships=relationships,
                )
        # Authentication is repeated after row-lock waits and writes, before commit.
        authenticate(db, request.cookies.get(COOKIE_NAME), clock)
    if rejected:
        raise rejected
    return response


@router.post(
    "/investigations/{investigation_id}/threads/{thread_kind}/cases/{case_id}/evidence-requests",
    response_model=CaseEvidence,
)
def inspect_evidence(
    investigation_id: UUID,
    thread_kind: ThreadKind,
    case_id: LocalID,
    payload: EvidenceRequestCreate,
    request: Request,
    visitor: CurrentVisitor,
    clock: Annotated[Clock, Depends(get_clock)],
):
    if request.query_params:
        raise APIError(422, "VALIDATION_ERROR", "Query overrides are not supported.")
    try:
        request_id, version, criteria, sources, inventory, end = start(
            request,
            investigation_id,
            thread_kind,
            case_id,
            payload,
            clock,
        )
        outcomes = collect(request, criteria, sources, inventory, end)
        return finalize(
            request,
            investigation_id,
            thread_kind,
            case_id,
            payload.state_id,
            request_id,
            version,
            outcomes,
            clock,
        )
    except SQLAlchemyError:
        # A committed start is retained; a failed final transaction returns no unrecorded evidence.
        raise failure() from None
