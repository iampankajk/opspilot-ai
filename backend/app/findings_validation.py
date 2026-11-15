"""Assemble only the selected returned evidence; validate references without semantic claims."""

import re

from sqlalchemy import select

from app.catalog import canonical_digest
from app.evidence import basis, record_chronology
from app.evidence_schemas import QUERY_SOURCES, EvidenceRelationshipView
from app.findings_schemas import FindingGenerationOutput, GroundedOutcome, GroundedRecord
from app.materialization import materialize_state
from app.models import (
    CaseEvidenceLink,
    DatasetVersion,
    EvidenceRecord,
    EvidenceRelationship,
    InvestigationState,
    RequestSource,
    RetrievalResult,
    RetrievalResultRecord,
    StateSource,
)


def resolve_pointer(record: dict, pointer: str):
    """RFC 6901 resolution, including escaped slashes and strict JSON array indexes."""
    if not pointer.startswith(("/payload/", "/timestamps/")) or re.search(r"~(?![01])", pointer):
        raise ValueError("Invalid evidence locator")
    value = record
    for segment in pointer[1:].split("/"):
        key = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
            index = int(key)
            if index >= len(value):
                raise ValueError("Missing array item")
            value = value[index]
        else:
            raise ValueError("Missing evidence field")
    return value


def evidence_bundle(db, draft, operation):
    # Also proves the complete persisted synthetic graph matches its pinned approved manifest.
    materialize_state(db, draft.investigation_id)
    state = db.get(InvestigationState, draft.state_id)
    dataset = db.get(DatasetVersion, state.dataset_version_id)
    manifest = next(c for c in dataset.manifest["cases"] if c["case_id"] == operation.case_id)
    requested = set(
        db.scalars(
            select(RequestSource.source_key).where(
                RequestSource.state_id == draft.state_id,
                RequestSource.request_id == operation.request_id,
            )
        )
    )
    results = db.scalars(
        select(RetrievalResult).where(
            RetrievalResult.state_id == draft.state_id,
            RetrievalResult.request_id == operation.request_id,
        )
    ).all()
    if requested != set(QUERY_SOURCES) or {r.source_key for r in results} != requested:
        raise ValueError("Incomplete source outcomes")
    memberships = db.scalars(
        select(RetrievalResultRecord)
        .where(
            RetrievalResultRecord.state_id == draft.state_id,
            RetrievalResultRecord.request_id == operation.request_id,
        )
        .limit(15)
    ).all()
    if len(memberships) > 14:
        raise ValueError("Evidence overflow")
    grouped = {key: [] for key in QUERY_SOURCES}
    for member in memberships:
        row = db.get(EvidenceRecord, (draft.state_id, member.evidence_record_id))
        link = db.get(
            CaseEvidenceLink, (draft.state_id, operation.case_id, member.evidence_record_id)
        )
        if (
            row is None
            or link is None
            or row.evidence_record_id not in manifest["evidence_record_ids"]
        ):
            raise ValueError("Record outside selected case")
        association = basis(link)
        if member.match_basis != association.model_dump(mode="json"):
            raise ValueError("Association basis mismatch")
        grouped[member.source_key].append(
            GroundedRecord(
                evidence_record_id=row.evidence_record_id,
                source_key=row.source_key,
                source_name=row.source_name,
                record_type=row.record_type,
                source_record_reference=row.source_record_reference,
                fixture_provenance=row.fixture_provenance,
                timestamps=row.timestamps,
                payload=row.payload,
                case_association=association,
                field_provenance=row.field_provenance,
            )
        )
    outcomes = []
    for result in sorted(results, key=lambda r: QUERY_SOURCES.index(r.source_key)):
        source = db.get(StateSource, (draft.state_id, result.source_key))
        outcomes.append(
            GroundedOutcome(
                source_key=result.source_key,
                source_name=source.source_name,
                **{
                    field: getattr(result, field)
                    for field in (
                        "execution_status",
                        "availability",
                        "match_status",
                        "returned_count",
                        "scope",
                        "completeness",
                        "limitations",
                        "error_code",
                    )
                },
                records=sorted(grouped[result.source_key], key=record_chronology),
            )
        )
    completed = sum(o.execution_status == "completed" for o in outcomes)
    if (operation.status == "completed" and completed != 6) or (
        operation.status == "partial" and not 0 < completed < 6
    ):
        raise ValueError("Request and source outcome mismatch")
    ids = {m.evidence_record_id for m in memberships}
    links = db.scalars(
        select(EvidenceRelationship)
        .where(
            EvidenceRelationship.state_id == draft.state_id,
            EvidenceRelationship.from_record_id.in_(ids),
            EvidenceRelationship.to_record_id.in_(ids),
        )
        .order_by(EvidenceRelationship.relationship_id)
        .limit(15)
    ).all()
    if len(links) > 14:
        raise ValueError("Relationship overflow")
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
    return {
        "dataset_version": dataset.version_label,
        "fixture_digest": dataset.fixture_digest,
        "source_outcomes": [o.model_dump(mode="json") for o in outcomes],
        "relationships": [r.model_dump(mode="json") for r in relationships],
    }


def returned_records(bundle):
    return {
        record["evidence_record_id"]: record
        for outcome in bundle["evidence"]["source_outcomes"]
        for record in outcome["records"]
    }


def validate_references(output: FindingGenerationOutput, bundle: dict) -> None:
    records = returned_records(bundle)
    sources = {s["source_key"] for s in bundle["evidence"]["source_outcomes"]}
    claims = set()
    for finding in output.findings:
        normalized = " ".join(finding.claim.casefold().split())
        if normalized in claims:
            raise ValueError("Duplicate claim")
        claims.add(normalized)
        targets = set()
        for citation in finding.citations:
            record = records.get(citation.evidence_record_id)
            if record is None:
                raise ValueError("Citation was not returned by selected request")
            resolve_pointer(record, citation.pointer)
            target = (citation.evidence_record_id, citation.pointer, citation.role)
            if target in targets:
                raise ValueError("Duplicate citation")
            targets.add(target)
        for statement in finding.rationale + finding.limitations:
            if any(i >= len(finding.citations) for i in statement.citation_indexes):
                raise ValueError("Citation index outside finding")
            if not set(statement.result_source_keys) <= sources:
                raise ValueError("Unknown retrieval outcome")
        if finding.proposed_status == "confirmed" and not any(
            c.role == "supports" for c in finding.citations
        ):
            raise ValueError("Confirmed requires a supporting record")
        if finding.proposed_status == "not_confirmed" and not finding.citations:
            raise ValueError("Not confirmed requires examined records")
        if not finding.citations and (
            finding.proposed_status != "inconclusive"
            or finding.kind == "hypothesis"
            and not any(s.kind == "unverified_hypothesis" for s in finding.rationale)
        ):
            raise ValueError("Uncited hypothesis must remain unverified and inconclusive")


def bundle_digest(bundle):
    return canonical_digest(bundle)
