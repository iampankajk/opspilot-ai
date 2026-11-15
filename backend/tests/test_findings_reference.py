# ruff: noqa: F811 -- pytest injects imported shared fixtures.
"""Repeatable offline reference checks. These are not live-model quality evaluations."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from test_evidence import retrieve
from test_findings import (
    ControlledProvider,
    attempts,
    generate,
    graph_counts,
    output_transform,
    prepare,
)
from test_findings import enabled as enabled
from test_investigations import context, create  # noqa: F401

from app import catalog, evidence, materialization
from app.catalog import FixtureBundle, canonical_digest, load_fixture
from app.findings_schemas import FindingGenerationOutput
from app.findings_validation import resolve_pointer, validate_references
from app.fixture_projection import projected_graph
from app.models import DatasetVersion, EvidenceRecord, InvestigationState

REFERENCE = json.loads((Path(__file__).parent / "fixtures/findings-reference.json").read_text())


def injection_dataset(connection, workspace, attack, monkeypatch):
    """A separately approved TEST registry entry with full digest/projection validation."""
    baseline, _ = load_fixture("synthetic-payments-v0.1")
    raw = baseline.model_dump(mode="json")
    raw["version_label"] = "synthetic-task5-injection-" + uuid4().hex
    ticket = next(r for r in raw["records"] if r["record_id"] == "SYN-ZD-TICKET-002")
    ticket["payload"]["Untrusted test comment"] = attack
    ticket["raw_markdown"] += "\n\nUntrusted test comment: " + attack
    ticket["payload_digest"] = canonical_digest(ticket["payload"])
    bundle = FixtureBundle.model_validate(raw)
    digest = canonical_digest(bundle.model_dump(mode="json"))
    monkeypatch.setitem(
        catalog.APPROVED_FIXTURES, bundle.version_label, ("test-only-not-loaded", digest)
    )

    def test_projection(selected, state_id):
        if selected.version_label != bundle.version_label:
            return projected_graph(selected, state_id)
        # Reuse the identical v0.1 record/case topology for this declared test-only version.
        graph = projected_graph(
            selected.model_copy(update={"version_label": baseline.version_label}), state_id
        )
        for record in graph[EvidenceRecord]:
            record["fixture_provenance"]["version_label"] = selected.version_label
        return graph

    monkeypatch.setattr(materialization, "projected_graph", test_projection)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        state = db.get(InvestigationState, UUID(workspace["state_id"]))
        dataset = DatasetVersion(
            version_label=bundle.version_label,
            fixture_digest=digest,
            manifest=bundle.manifest(),
            provenance={"origin": "synthetic test overlay"},
        )
        db.add(dataset)
        db.flush()
        state.dataset_version_id = dataset.dataset_version_id
        for model, values in test_projection(bundle, state.state_id).items():
            primary = [c.name for c in model.__table__.primary_key]
            for entry in values:
                row = db.get(model, tuple(entry[c] for c in primary))
                for key, value in entry.items():
                    setattr(row, key, value)


@pytest.mark.parametrize("repetition", range(3))
@pytest.mark.parametrize("probe", REFERENCE["cases"], ids=lambda p: p["id"])
def test_approved_reference_cases_with_offline_provider(enabled, monkeypatch, probe, repetition):
    client, connection, app, _, _ = enabled
    thread, case = probe["thread"], probe["case"]
    if probe["kind"] == "missing_provider":
        original = evidence.read_source

        def fail_provider(request, criteria, key, inventory, end):
            if key == probe["failed_source"]:
                raise RuntimeError("Synthetic provider retrieval failure")
            return original(request, criteria, key, inventory, end)

        monkeypatch.setattr(evidence, "read_source", fail_provider)
    if probe["kind"] == "injection":
        workspace = create(client).json()
        injection_dataset(connection, workspace, probe["attack"], monkeypatch)
        inspected = retrieve(client, workspace, thread, case)
        assert inspected.status_code == 200, inspected.text
        workspace |= {
            "draft_version": inspected.json()["draft_version"],
            "evidence_request_id": inspected.json()["evidence_request_id"],
        }
    else:
        workspace = prepare(client, thread, case)
    if probe["kind"] == "invalid_references":

        def invalid(output):
            output["findings"][0]["citations"][0]["evidence_record_id"] = "SYN-INVENTED"

        app.state.findings_provider = ControlledProvider(output_transform(invalid))
        response = generate(client, workspace, thread, case)
        assert response.status_code == 502
        assert graph_counts(connection, workspace) == [0] * 5
        return
    response = generate(client, workspace, thread, case)
    assert response.status_code == 201, response.text
    body = response.json()
    operation = attempts(connection, workspace)[0]
    parsed = FindingGenerationOutput.model_validate(operation.normalized_output)
    validate_references(parsed, operation.input_bundle)
    if probe["kind"] in {"semantic", "missing_provider"}:
        claims = [probe["claim"]]
        if "also_claim" in probe:
            claims.append(probe["also_claim"])
        for claim in claims:
            item = next(f for f in body["findings"] if f["claim"] == claim)
            assert item["proposed_status"] == probe["status"]
            cited = {(c["evidence_record_id"], c["pointer"]) for c in item["citations"]}
            assert {tuple(p) for p in probe.get("fields", [])} <= cited, claim
        if probe["kind"] == "missing_provider":
            outcomes = {o["source_key"]: o for o in body["source_outcomes"]}
            assert outcomes["stripe"]["execution_status"] == "failed"
            assert outcomes["stripe"]["returned_count"] is None
            for key in probe["zero_sources"]:
                assert (
                    outcomes[key]["returned_count"] == 0
                    and outcomes[key]["match_status"] == "no_matches"
                )
            assert {r["source_key"] for r in item["result_refs"]} == {"stripe"}
            assert "SYN-STRIPE-DUP-001" not in {
                r["evidence_record_id"] for r in body["cited_records"]
            }
    else:
        assert probe["attack"] not in operation.input_bundle["instructions"]
        assert (
            "Untrusted test comment"
            in next(
                r
                for o in operation.input_bundle["evidence"]["source_outcomes"]
                for r in o["records"]
                if r["evidence_record_id"] == "SYN-ZD-TICKET-002"
            )["payload"]
        )
        assert operation.input_bundle["response_options"]["tools"] == []
        for finding in body["findings"]:
            assert finding["review_state"] == "awaiting_review"
            if "bank posted" in finding["claim"] or "charged only once" in finding["claim"]:
                assert finding["proposed_status"] == "inconclusive"
        assert "PRIVATE" not in response.text


def test_d03_manifest_requires_provider_and_customer_report_evidence():
    probe = next(p for p in REFERENCE["cases"] if p["id"] == "D-03")
    required = {
        ("SYN-STRIPE-DUP-001", "/payload/Returned lifecycle events"),
        ("SYN-STRIPE-DUP-001", "/payload/Extract scope and completeness"),
        ("SYN-STRIPE-DUP-001", "/payload/Settlement~1bank posting evidence"),
        ("SYN-ZD-TICKET-002", "/payload/Reported issue"),
        ("SYN-ZD-TICKET-002", "/payload/Bank~1issuer evidence"),
    }
    assert required <= {tuple(p) for p in probe["fields"]}
    assert probe["status"] == "inconclusive"


def test_reference_manifest_locators_and_timestamp_precision_are_real_fixture_fields():
    bundle, _ = load_fixture("synthetic-payments-v0.1")
    records = {r.record_id: {"payload": r.payload} for r in bundle.records}
    for probe in REFERENCE["cases"]:
        for record, pointer in probe.get("fields", []):
            assert resolve_pointer(records[record], pointer) is not None
    assert "minute precision" in records["SYN-PO-ATT-001"]["payload"]["Event time"]


def test_pointer_resolution_is_exact_and_does_not_invent_missing_values():
    record = {
        "payload": {"slash/key~": "value", "unknown": None},
        "timestamps": [{"precision": "minute"}],
    }
    assert resolve_pointer(record, "/payload/slash~1key~0") == "value"
    assert resolve_pointer(record, "/payload/unknown") is None
    assert resolve_pointer(record, "/timestamps/0/precision") == "minute"
    for pointer in (
        "/payload/missing",
        "/timestamps/01",
        "/timestamps/-",
        "/timestamps/5",
        "/raw_markdown",
    ):
        with pytest.raises(ValueError):
            resolve_pointer(record, pointer)
