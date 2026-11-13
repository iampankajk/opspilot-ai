import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, get_args
from uuid import UUID, uuid4

from pydantic import Field, ValidationError, model_validator
from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api_errors import APIError
from app.models import DatasetVersion, Incident
from app.workspace_schemas import (
    DatasetVersionResponse,
    IncidentContext,
    IncidentEntry,
    LocalID,
    Schema,
    SourceKey,
    ThreadKind,
)

BACKEND = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = BACKEND.parent / "docs" / "SYNTHETIC_EVIDENCE_PACKAGE.md"
# Developer-approved registry: no version sorting, runtime admin, or request-supplied paths.
APPROVED_FIXTURES = {
    "synthetic-payments-v0.1": (
        "synthetic-payments-v0.1.json",
        "043e93fa4ee85f48fb59ba06581891204efb0aadf8bfded2284b73170b293559",
    ),
}
SOURCE_NAMESPACE = "synthetic:pagerduty"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def dataset_unavailable() -> APIError:
    return APIError(
        503,
        "DATASET_UNAVAILABLE",
        "The configured synthetic dataset is unavailable or inconsistent.",
    )


class SourceCoverage(Schema):
    source_key: SourceKey
    source_name: str = Field(min_length=1)
    source_category: str = Field(min_length=1)
    availability: Literal["included", "not_included", "not_constructed", "unavailable"]
    scope: str | None
    completeness: Literal[
        "unverified", "known_partial", "verified_for_stated_scope", "not_applicable"
    ]
    limitations: list[str]


class FixtureRecord(Schema):
    record_id: LocalID
    source_key: SourceKey
    payload: dict[str, str]
    raw_markdown: str
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class FixtureCase(Schema):
    case_id: LocalID
    case_reference: LocalID
    primary_report_record_id: LocalID
    thread_kinds: list[ThreadKind] = Field(min_length=1, max_length=2)
    evidence_record_ids: list[LocalID] = Field(min_length=1)


class FixtureThread(Schema):
    thread_kind: ThreadKind
    label: str = Field(min_length=1)


class FixtureBundle(Schema):
    version_label: str
    source_package_sha256: str
    incident: dict[str, Any]
    sources: list[SourceCoverage] = Field(min_length=9, max_length=9)
    threads: list[FixtureThread] = Field(min_length=2, max_length=2)
    cases: list[FixtureCase] = Field(min_length=2, max_length=2)
    incident_context_record_ids: list[LocalID]
    declared_gaps: list[str]
    records: list[FixtureRecord] = Field(min_length=14, max_length=14)

    @model_validator(mode="after")
    def validate_graph(self):
        IncidentContext.model_validate(self.incident | {"incident_id": UUID(int=0)})
        record_ids = {r.record_id for r in self.records}
        if len(record_ids) != 14 or {s.source_key for s in self.sources} != set(
            get_args(SourceKey)
        ):
            raise ValueError("Incomplete or repeated source/record inventory")
        if {t.thread_kind for t in self.threads} != set(get_args(ThreadKind)):
            raise ValueError("Exactly two approved thread kinds are required")
        if (
            len({c.case_id for c in self.cases}) != 2
            or len({c.case_reference for c in self.cases}) != 2
        ):
            raise ValueError("Case identities must be unique")
        linked = set(self.incident_context_record_ids)
        for case in self.cases:
            refs = set(case.evidence_record_ids)
            if (
                not refs <= record_ids
                or case.primary_report_record_id not in refs
                or len(refs) != len(case.evidence_record_ids)
                or len(set(case.thread_kinds)) != len(case.thread_kinds)
            ):
                raise ValueError("Invalid case references or memberships")
            linked |= refs
        if linked != record_ids or self.incident["source_alert_record_id"] not in record_ids:
            raise ValueError("Missing incident/case record reference")
        if any(canonical_digest(r.payload) != r.payload_digest for r in self.records):
            raise ValueError("Source payload digest mismatch")
        return self

    def manifest(self) -> dict:
        # Metadata only. Relational case/evidence content is deferred to stage 003.
        result = self.model_dump(mode="json", exclude={"records"})
        result["records"] = [
            {
                "record_id": r.record_id,
                "source_key": r.source_key,
                "payload_digest": r.payload_digest,
            }
            for r in self.records
        ]
        return result


def load_fixture(version: str) -> tuple[FixtureBundle, str]:
    try:
        filename, digest = APPROVED_FIXTURES[version]
        raw = (BACKEND / "fixtures" / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Fixture digest mismatch")
        bundle = FixtureBundle.model_validate_json(raw)
        source = SOURCE_PACKAGE.read_bytes()
        if (
            bundle.version_label != version
            or hashlib.sha256(source).hexdigest() != bundle.source_package_sha256
        ):
            raise ValueError("Source package/version mismatch")
        expected_ids = set()
        for heading in source.decode().splitlines():
            if re.match(r"^#{3,4} Records? SYN-", heading):
                expected_ids.update(re.findall(r"SYN-[A-Z0-9-]+", heading))
        if expected_ids != {r.record_id for r in bundle.records}:
            raise ValueError("Source package inventory mismatch")
        return bundle, digest
    except (OSError, KeyError, ValueError, ValidationError):
        raise dataset_unavailable() from None


def register_catalog(engine: Engine, bundle: FixtureBundle, digest: str) -> IncidentEntry:
    manifest = bundle.manifest()
    with Session(engine) as db, db.begin():
        db.execute(
            insert(DatasetVersion)
            .values(
                dataset_version_id=uuid4(),
                version_label=bundle.version_label,
                fixture_digest=digest,
                manifest=manifest,
                provenance={
                    "origin": "constructed synthetic repository fixture",
                    "source_package_sha256": bundle.source_package_sha256,
                },
            )
            .on_conflict_do_nothing(index_elements=[DatasetVersion.version_label])
        )
        dataset = db.scalar(
            select(DatasetVersion).where(DatasetVersion.version_label == bundle.version_label)
        )
        if dataset.fixture_digest != digest or dataset.manifest != manifest:
            raise dataset_unavailable()
        db.execute(
            insert(Incident)
            .values(
                incident_id=uuid4(),
                source_namespace=SOURCE_NAMESPACE,
                source_incident_reference=bundle.incident["incident_ref"],
            )
            .on_conflict_do_nothing(
                index_elements=[Incident.source_namespace, Incident.source_incident_reference]
            )
        )
        incident = db.scalar(
            select(Incident).where(
                Incident.source_namespace == SOURCE_NAMESPACE,
                Incident.source_incident_reference == bundle.incident["incident_ref"],
            )
        )
        return IncidentEntry(
            incident=IncidentContext.model_validate(
                bundle.incident | {"incident_id": incident.incident_id}
            ),
            dataset_version=DatasetVersionResponse(
                dataset_version_id=dataset.dataset_version_id,
                version_label=dataset.version_label,
                fixture_digest=dataset.fixture_digest,
            ),
        )


def initialize_catalog(engine: Engine, version: str) -> IncidentEntry:
    bundle, digest = load_fixture(version)
    return register_catalog(engine, bundle, digest)
