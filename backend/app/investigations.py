import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.catalog import SourceCoverage
from app.materialization import materialize_state
from app.models import (
    CaseThread,
    DatasetVersion,
    Investigation,
    InvestigationState,
    PaymentCase,
    StateSource,
    ThreadState,
    WorkingDraft,
)
from app.visitor_sessions import COOKIE_NAME, Clock, CurrentVisitor, authenticate, get_clock
from app.workspace_schemas import (
    CaseList,
    CaseListQuery,
    CaseSummary,
    DatasetVersionResponse,
    IncidentContext,
    IncidentEntry,
    InvestigationCreate,
    LocalID,
    Money,
    ThreadKind,
    Workspace,
    WorkspaceThread,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
THREAD_ORDER = ("payment_failures", "possible_duplicates")


def not_found() -> APIError:
    return APIError(404, "NOT_FOUND", "Resource not found.")


def initialization_failed() -> APIError:
    return APIError(
        503,
        "INITIALIZATION_FAILED",
        "The investigation workspace could not be initialized or loaded.",
    )


def no_query_overrides(request: Request) -> None:
    if request.query_params:
        raise APIError(
            422, "VALIDATION_ERROR", "Query overrides are not supported on this endpoint."
        )


def current_catalog(request: Request) -> IncidentEntry:
    if request.app.state.catalog_error:
        raise request.app.state.catalog_error
    return request.app.state.catalog


def workspace_view(db: Session, investigation: Investigation) -> Workspace:
    draft = db.get(WorkingDraft, investigation.investigation_id)
    if draft is None:
        raise initialization_failed()
    state = db.scalar(
        select(InvestigationState).where(
            InvestigationState.state_id == draft.state_id,
            InvestigationState.investigation_id == investigation.investigation_id,
        )
    )
    if state is None:
        raise initialization_failed()
    dataset = db.get(DatasetVersion, state.dataset_version_id)
    threads = db.scalars(select(ThreadState).where(ThreadState.state_id == state.state_id)).all()
    sources = db.scalars(select(StateSource).where(StateSource.state_id == state.state_id)).all()
    if {source.source_key for source in sources} != {
        source["source_key"] for source in dataset.manifest["sources"]
    }:
        raise initialization_failed()
    counts = dict(
        db.execute(
            select(CaseThread.thread_kind, func.count())
            .where(CaseThread.state_id == state.state_id)
            .group_by(CaseThread.thread_kind)
        ).all()
    )
    labels = {thread.thread_kind: thread.presentation["label"] for thread in threads}
    if set(labels) != set(THREAD_ORDER):
        raise initialization_failed()
    return Workspace(
        investigation_id=investigation.investigation_id,
        state_id=state.state_id,
        draft_version=draft.draft_version,
        dataset_version=DatasetVersionResponse(
            dataset_version_id=dataset.dataset_version_id,
            version_label=dataset.version_label,
            fixture_digest=dataset.fixture_digest,
        ),
        incident=IncidentContext.model_validate(state.incident_context),
        threads=[
            WorkspaceThread(
                thread_kind=kind,
                label=labels[kind],
                case_count=counts.get(kind, 0),
            )
            for kind in THREAD_ORDER
        ],
    )


def initialize_graph(db: Session, investigation: Investigation, catalog: IncidentEntry) -> None:
    dataset = db.get(DatasetVersion, catalog.dataset_version.dataset_version_id)
    state = InvestigationState(
        investigation_id=investigation.investigation_id,
        dataset_version_id=dataset.dataset_version_id,
        incident_context=catalog.incident.model_dump(mode="json"),
        limitations=list(dataset.manifest["declared_gaps"]),
    )
    db.add(state)
    db.flush()
    db.add(
        WorkingDraft(
            investigation_id=investigation.investigation_id,
            state_id=state.state_id,
            draft_version=0,
            has_unversioned_changes=True,
        )
    )
    for thread in dataset.manifest["threads"]:
        db.add(
            ThreadState(
                state_id=state.state_id,
                thread_kind=thread["thread_kind"],
                summary=None,
                limitations=list(dataset.manifest["declared_gaps"]),
                unresolved_questions=[],
                presentation={"label": thread["label"]},
            )
        )
    for source in dataset.manifest["sources"]:
        coverage = SourceCoverage.model_validate(source)
        db.add(StateSource(state_id=state.state_id, **coverage.model_dump()))
    db.flush()
    materialize_state(db, investigation.investigation_id, initial=True)


def checked_view(
    db: Session, request: Request, investigation: Investigation, clock: Clock
) -> Workspace:
    materialize_state(db, investigation.investigation_id)
    result = workspace_view(db, investigation)
    actor = authenticate(db, request.cookies.get(COOKIE_NAME), clock)
    if actor.visitor_context_id != investigation.visitor_context_id:
        raise not_found()
    return result


def create_or_resume(request: Request, incident_id: UUID, clock: Clock) -> tuple[Workspace, bool]:
    try:
        with Session(request.app.state.engine) as db, db.begin():
            actor = authenticate(db, request.cookies.get(COOKIE_NAME), clock)
            existing = db.scalar(
                select(Investigation)
                .where(
                    Investigation.visitor_context_id == actor.visitor_context_id,
                    Investigation.incident_id == incident_id,
                )
                .with_for_update()
            )
            if existing is not None:
                return checked_view(db, request, existing, clock), False
            catalog = current_catalog(request)
            if catalog.incident.incident_id != incident_id:
                raise not_found()
            investigation = Investigation(
                visitor_context_id=actor.visitor_context_id, incident_id=incident_id
            )
            db.add(investigation)
            db.flush()
            initialize_graph(db, investigation, catalog)
            return checked_view(db, request, investigation, clock), True
    except IntegrityError as exc:
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            != "uq_investigations_visitor_context_id"
        ):
            raise
        # The losing graph is rolled back. Read the committed winner in a fresh transaction.
        with Session(request.app.state.engine) as db, db.begin():
            actor = authenticate(db, request.cookies.get(COOKIE_NAME), clock)
            winner = db.scalar(
                select(Investigation)
                .where(
                    Investigation.visitor_context_id == actor.visitor_context_id,
                    Investigation.incident_id == incident_id,
                )
                .with_for_update()
            )
            if winner is None:
                raise initialization_failed() from None
            return checked_view(db, request, winner, clock), False


@router.get("/incidents/{incident_ref}", response_model=IncidentEntry)
def incident_entry(incident_ref: LocalID, request: Request, visitor: CurrentVisitor):
    no_query_overrides(request)
    catalog = current_catalog(request)
    if catalog.incident.incident_ref != incident_ref:
        raise not_found()
    return catalog


@router.post(
    "/investigations",
    response_model=Workspace,
    status_code=201,
    responses={200: {"model": Workspace}},
)
def investigation_create(
    payload: InvestigationCreate,
    request: Request,
    response: Response,
    visitor: CurrentVisitor,
    clock: Annotated[Clock, Depends(get_clock)],
):
    no_query_overrides(request)
    try:
        result, created = create_or_resume(request, payload.incident_id, clock)
    except (RuntimeError, ValueError, KeyError) as exc:
        logger.error(
            "Initialization failed: request_id=%s exception_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        raise initialization_failed() from None
    response.status_code = 201 if created else 200
    return result


@router.get("/investigations/{investigation_id}/workspace", response_model=Workspace)
def investigation_workspace(
    investigation_id: UUID,
    request: Request,
    visitor: CurrentVisitor,
    clock: Annotated[Clock, Depends(get_clock)],
):
    no_query_overrides(request)
    with Session(request.app.state.engine) as db, db.begin():
        investigation = db.scalar(
            select(Investigation)
            .where(
                Investigation.investigation_id == investigation_id,
                Investigation.visitor_context_id == visitor.visitor_context_id,
            )
            .with_for_update()
        )
        if investigation is None:
            raise not_found()
        return checked_view(db, request, investigation, clock)


@router.get(
    "/investigations/{investigation_id}/threads/{thread_kind}/cases", response_model=CaseList
)
def thread_cases(
    investigation_id: UUID,
    thread_kind: ThreadKind,
    query: Annotated[CaseListQuery, Query()],
    request: Request,
    visitor: CurrentVisitor,
    clock: Annotated[Clock, Depends(get_clock)],
):
    with Session(request.app.state.engine) as db, db.begin():
        investigation = db.scalar(
            select(Investigation)
            .where(
                Investigation.investigation_id == investigation_id,
                Investigation.visitor_context_id == visitor.visitor_context_id,
            )
            .with_for_update()
        )
        if investigation is None:
            raise not_found()
        draft = db.get(WorkingDraft, investigation_id)
        if draft is None:
            raise initialization_failed()
        if draft.state_id != query.state_id:
            raise APIError(409, "STALE_STATE", "Reload the workspace before selecting cases.")
        if db.get(ThreadState, (draft.state_id, thread_kind)) is None:
            raise not_found()
        materialize_state(db, investigation_id)
        # The same state participates in every join; local IDs alone never select data.
        cases = db.scalars(
            select(PaymentCase)
            .join(
                CaseThread,
                (CaseThread.state_id == PaymentCase.state_id)
                & (CaseThread.case_id == PaymentCase.case_id),
            )
            .where(
                PaymentCase.state_id == query.state_id,
                CaseThread.thread_kind == thread_kind,
            )
            .order_by(PaymentCase.case_reference)
        ).all()
        result = CaseList(
            investigation_id=investigation_id,
            state_id=draft.state_id,
            draft_version=draft.draft_version,
            thread_kind=thread_kind,
            cases=[
                CaseSummary(
                    case_id=case.case_id,
                    case_reference=case.case_reference,
                    primary_report_record_id=case.primary_report_record_id,
                    customer_ref=case.customer_ref,
                    reported_order_ref=case.reported_order_ref,
                    related_order_refs=case.related_order_refs,
                    reported_issue=case.reported_issue,
                    reported_money=Money(
                        amount=str(case.reported_amount), currency=case.reported_currency
                    )
                    if case.reported_amount is not None
                    else None,
                    reported_at=case.reported_at,
                    payment_state=case.payment_state,
                )
                for case in cases
            ],
        )
        actor = authenticate(db, request.cookies.get(COOKIE_NAME), clock)
        if actor.visitor_context_id != investigation.visitor_context_id:
            raise not_found()
        return result
