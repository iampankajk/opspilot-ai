import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.catalog import FixtureCase, SourceCoverage
from app.models import (
    DatasetVersion,
    Investigation,
    InvestigationState,
    StateSource,
    ThreadState,
    WorkingDraft,
)
from app.visitor_sessions import COOKIE_NAME, Clock, CurrentVisitor, authenticate, get_clock
from app.workspace_schemas import (
    DatasetVersionResponse,
    IncidentContext,
    IncidentEntry,
    InvestigationCreate,
    LocalID,
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
    # These counts are configured fixture memberships for Task 3, not initialized case rows.
    cases = [FixtureCase.model_validate(case) for case in dataset.manifest["cases"]]
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
                case_count=sum(kind in case.thread_kinds for case in cases),
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


def checked_view(
    db: Session, request: Request, investigation: Investigation, clock: Clock
) -> Workspace:
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
                select(Investigation).where(
                    Investigation.visitor_context_id == actor.visitor_context_id,
                    Investigation.incident_id == incident_id,
                )
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
                select(Investigation).where(
                    Investigation.visitor_context_id == actor.visitor_context_id,
                    Investigation.incident_id == incident_id,
                )
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
            select(Investigation).where(
                Investigation.investigation_id == investigation_id,
                Investigation.visitor_context_id == visitor.visitor_context_id,
            )
        )
        if investigation is None:
            raise not_found()
        return checked_view(db, request, investigation, clock)
