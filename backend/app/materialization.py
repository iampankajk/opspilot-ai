from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.catalog import APPROVED_FIXTURES, FixtureBundle, dataset_unavailable, load_fixture
from app.fixture_projection import projected_graph
from app.models import (
    CaseEvidenceLink,
    CaseThread,
    DatasetVersion,
    EvidenceRecord,
    EvidenceRelationship,
    InvestigationState,
    PaymentCase,
    WorkingDraft,
)

GRAPH_MODELS = (EvidenceRecord, PaymentCase, CaseThread, CaseEvidenceLink, EvidenceRelationship)


def materialization_failed() -> APIError:
    return APIError(
        503,
        "INITIALIZATION_FAILED",
        "The state's case/evidence data are incomplete or inconsistent.",
    )


def persist_graph(db: Session, graph: dict) -> None:
    # Flush each dependency boundary; repositories never commit independently.
    for model in GRAPH_MODELS:
        db.add_all(model(**values) for values in graph[model])
        db.flush()


def materialize_state(db: Session, investigation_id: UUID, *, initial: bool = False) -> bool:
    """Caller holds the investigation-row lock (or owns its uncommitted insert)."""
    draft = db.get(WorkingDraft, investigation_id)
    if draft is None:
        raise materialization_failed()
    state = db.scalar(
        select(InvestigationState).where(
            InvestigationState.state_id == draft.state_id,
            InvestigationState.investigation_id == investigation_id,
        )
    )
    if state is None:
        raise materialization_failed()
    dataset = db.get(DatasetVersion, state.dataset_version_id)
    stored = {
        model: db.scalars(select(model).where(model.state_id == state.state_id)).all()
        for model in GRAPH_MODELS
    }
    populated = any(stored.values())
    try:
        if not populated:
            bundle, digest = load_fixture(dataset.version_label)
        else:
            # Once persisted, reads need no current fixture file or configured version.
            entries = [
                {
                    "record_id": row.evidence_record_id,
                    "source_key": row.source_key,
                    "payload": row.payload,
                    "raw_markdown": row.raw_markdown,
                    "payload_digest": row.source_digest,
                }
                for entry in dataset.manifest["records"]
                for row in stored[EvidenceRecord]
                if row.evidence_record_id == entry["record_id"]
            ]
            bundle = FixtureBundle.model_validate(dataset.manifest | {"records": entries})
            digest = APPROVED_FIXTURES[dataset.version_label][1]
        if digest != dataset.fixture_digest or bundle.manifest() != dataset.manifest:
            raise dataset_unavailable()
        graph = projected_graph(bundle, state.state_id)
        if populated:
            for model in GRAPH_MODELS:
                primary = [column.name for column in model.__table__.primary_key]
                actual = {tuple(getattr(row, key) for key in primary): row for row in stored[model]}
                expected = {
                    tuple(values[key] for key in primary): values for values in graph[model]
                }
                if actual.keys() != expected.keys() or any(
                    getattr(actual[key], field) != value
                    for key, values in expected.items()
                    for field, value in values.items()
                ):
                    raise materialization_failed()
            return False
        persist_graph(db, graph)
        if not initial:
            draft.draft_version += 1
            draft.has_unversioned_changes = True
            draft.persisted_at = datetime.now(UTC)
        db.flush()
        return True
    except (KeyError, ValueError, ValidationError, RuntimeError):
        raise materialization_failed() from None
