"""Deterministic v0.1 field projection; the reviewed fixture content stays immutable."""

import re
from datetime import datetime
from decimal import Decimal

from app.catalog import FixtureBundle
from app.models import (
    CaseEvidenceLink,
    CaseThread,
    EvidenceRecord,
    EvidenceRelationship,
    PaymentCase,
)
from app.workspace_schemas import AssociationBasis, SourceTime

F = "SYN-PO-ATT-001"
A, B = "SYN-PO-ATT-002-A", "SYN-PO-ATT-002-B"
TF, TD = "SYN-ZD-TICKET-001", "SYN-ZD-TICKET-002"
SF, SD = "SYN-STRIPE-FAIL-001", "SYN-STRIPE-DUP-001"
H, E = "SYN-ZD-HANDOFF-001", "SYN-ZD-ESCALATION-001"
LOG, TRACE = "SYN-LOKI-FAIL-001", "SYN-TEMPO-FAIL-001"


def identifiers(value: str) -> set[str]:
    return set(re.findall(r"SYN-[A-Z0-9-]+", value))


def source_time(raw: str, role: str) -> dict:
    values = list(dict.fromkeys(re.findall(r"2026-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z", raw)))
    precision = "unknown"
    if values:
        precision = (
            "minute_range"
            if len(values) > 1
            else ("second" if values[0].count(":") == 2 else "minute")
        )
    return SourceTime(
        role=role,
        raw=raw,
        timezone="Asia/Singapore" if "SGT" in raw else ("UTC" if values else None),
        precision=precision,
        utc_lower=datetime.fromisoformat(values[0]) if values else None,
        utc_upper=datetime.fromisoformat(values[-1]) if values else None,
        missing_reason=None
        if values
        else "No event-specific UTC timestamp is constructed in this field.",
    ).model_dump(mode="json")


def record_times(record) -> list[dict]:
    payload = record.payload
    times = [
        source_time(value, key)
        for key, value in sorted(payload.items())
        if key in {"Event time", "Event timestamp", "Created"} or key.startswith("Event timestamp")
    ]
    if "Capture event time" in payload:
        times.append(source_time(payload["Capture event time"], "Capture event time"))
    if record.source_key == "deployment_history":
        for line in record.raw_markdown.splitlines():
            if line.startswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) == 3 and "2026-" in cells[2]:
                    times.append(source_time(cells[1] + " SGT / " + cells[2], cells[0]))
    return times


def projected_graph(bundle: FixtureBundle, state_id) -> dict[type, list[dict]]:
    if bundle.version_label != "synthetic-payments-v0.1":
        raise ValueError("No approved projection exists for this fixture version")
    records = {record.record_id: record for record in bundle.records}
    sources = {source.source_key: source for source in bundle.sources}
    graph = {
        EvidenceRecord: [],
        PaymentCase: [],
        CaseThread: [],
        CaseEvidenceLink: [],
        EvidenceRelationship: [],
    }
    types = {
        "incident_alert": "alert",
        "metrics": "metric_series",
        "deployment_history": "deployment_timeline",
        "internal_payments": "attempt",
        "stripe": "provider_extract",
        "zendesk": "ticket",
        "support_lookup": "lookup",
        "loki": "log",
        "tempo": "trace",
    }
    for record in bundle.records:
        payload = record.payload
        reference = None
        identity_field = payload.get("Ticket reference", payload.get("Transaction / attempt", ""))
        if record.record_id in identifiers(identity_field):
            reference = record.record_id
        graph[EvidenceRecord].append(
            dict(
                state_id=state_id,
                evidence_record_id=record.record_id,
                source_key=record.source_key,
                source_name=payload.get("Source system", sources[record.source_key].source_name),
                record_type="escalation" if record.record_id == E else types[record.source_key],
                source_record_reference=reference,
                fixture_provenance={
                    "version_label": bundle.version_label,
                    "fixture_record_id": record.record_id,
                    "origin": payload.get(
                        "Provenance",
                        payload.get("source_provenance", "Constructed synthetic fixture"),
                    ),
                },
                source_digest=record.payload_digest,
                payload=dict(payload),
                raw_markdown=record.raw_markdown,
                timestamps=record_times(record),
                field_provenance={
                    "attribution": payload.get(
                        "Identifier provenance",
                        payload.get("Provenance", payload.get("source_provenance")),
                    ),
                    "source_fields": sorted(payload),
                },
            )
        )

    def relationship(
        key,
        left,
        right,
        category,
        left_fields,
        right_fields,
        basis,
        explanation,
        limitations=(),
        shared=True,
    ):
        lvalues = {field: records[left].payload[field] for field in left_fields}
        rvalues = {field: records[right].payload[field] for field in right_fields}
        common = identifiers(" ".join(lvalues.values())) & identifiers(" ".join(rvalues.values()))
        if shared and not common:
            raise ValueError("A claimed identifier relationship has no shared source identifier")
        fields = {
            "from_fields": lvalues,
            "to_fields": rvalues,
            "matching_identifiers": sorted(common),
        }
        graph[EvidenceRelationship].append(
            dict(
                state_id=state_id,
                relationship_id=key,
                from_record_id=left,
                to_record_id=right,
                category=category,
                matched_fields=fields,
                explanation=explanation,
                basis_record_id=basis,
                attribution="Explicit synthetic source fields; application-labelled relationship",
                limitations=list(limitations),
            )
        )

    relationship(
        "failure-report-attempt",
        TF,
        F,
        "field_match",
        ["Customer reference", "Order reference"],
        ["Customer / order"],
        TF,
        "Trusted portal customer and order fields match the internal attempt; "
        "no customer-supplied transaction ID is invented.",
    )
    relationship(
        "failure-attempt-provider",
        F,
        SF,
        "direct_ref_match",
        ["Provider reference / request"],
        ["Payment Intent", "Related provider request"],
        SF,
        "The provider extract explicitly identifies the same provider request and Payment Intent.",
        ["Provider completeness is unverified; a timeout is not proof of provider failure."],
    )
    relationship(
        "failure-attempt-log",
        F,
        LOG,
        "direct_ref_match",
        ["Transaction / attempt", "Provider reference / request"],
        ["Attempt / provider request"],
        LOG,
        "The log explicitly identifies the attempt/provider request.",
    )
    relationship(
        "failure-attempt-trace",
        F,
        TRACE,
        "direct_ref_match",
        ["Transaction / attempt", "Provider reference / request"],
        ["Related attempt/request"],
        TRACE,
        "The trace explicitly identifies the attempt/provider request.",
    )
    relationship(
        "failure-log-trace",
        LOG,
        TRACE,
        "field_match",
        ["Trace ID"],
        ["Trace ID"],
        LOG,
        "The log and trace share the explicit trace identifier; this does not "
        "establish root cause.",
    )
    relationship(
        "duplicate-ticket-lookup",
        TD,
        H,
        "direct_ref_match",
        ["Ticket reference"],
        ["Related ticket"],
        H,
        "The original Support lookup history names this ticket; it is not a new OpsPilot query.",
    )
    relationship(
        "duplicate-ticket-escalation",
        TD,
        E,
        "direct_ref_match",
        ["Ticket reference"],
        ["Related ticket"],
        E,
        "The escalation packet names the ticket; its omitted lookup details stay omitted.",
    )
    for attempt, suffix in ((A, "a"), (B, "b")):
        relationship(
            f"lookup-attempt-{suffix}",
            H,
            attempt,
            "documented_lookup",
            ["Candidate records returned"],
            ["Transaction / attempt"],
            H,
            "The recorded Support lookup returned this candidate attempt; it is "
            "not a definitive financial match.",
        )
        relationship(
            f"duplicate-attempt-{suffix}-provider",
            attempt,
            SD,
            "direct_ref_match",
            ["Provider request reference"],
            ["Provider requests"],
            SD,
            "The provider extract explicitly lists this candidate attempt's request reference.",
            [
                "Provider completeness is unverified; settlement and bank posting are "
                "not constructed."
            ],
        )
    relationship(
        "duplicate-attempts-idempotency",
        A,
        B,
        "field_match",
        ["Idempotency key"],
        ["Idempotency key"],
        A,
        "The attempts share the source idempotency key; reuse is not proof of "
        "deduplication or duplicate charges.",
    )
    relationship(
        "alert-metric-context",
        "SYN-PD-ALERT-001",
        "SYN-GRAF-METRIC-001",
        "temporal_context",
        ["Measurement window", "Region"],
        ["Window", "Region"],
        "SYN-PD-ALERT-001",
        "The aggregate metric supplies the alert's APAC window context.",
        ["Time-window association is not causation."],
        shared=False,
    )
    relationship(
        "deployment-failure-context",
        "SYN-DEPLOYMENT-TIMELINE-001",
        F,
        "temporal_context",
        ["timeline_markdown"],
        ["Event time"],
        "SYN-DEPLOYMENT-TIMELINE-001",
        "The coarse deployment timeline is earlier timing context only.",
        ["No deployment success or causal relationship is established."],
        shared=False,
    )

    for case in bundle.cases:
        report = records[case.primary_report_record_id].payload
        currency, amount = report["Reported amount/currency"].split()
        orders = identifiers(report["Order reference"])
        related = []
        if H in case.evidence_record_ids:
            candidate = next(
                value
                for value in identifiers(records[H].payload["Search result"])
                if value.startswith("SYN-ORD-")
            )
            related = [{"value": candidate, "association": "candidate", "basis_record_id": H}]
        payment_state = None
        if F in case.evidence_record_ids:
            payment_state = {
                "label": records[F].payload["Internal status"],
                "basis_record_ids": [F],
                "limitations": [
                    "The internal timeout does not establish provider failure or bank posting."
                ],
            }
        graph[PaymentCase].append(
            dict(
                state_id=state_id,
                case_id=case.case_id,
                case_reference=case.case_reference,
                primary_report_record_id=case.primary_report_record_id,
                customer_ref=next(iter(identifiers(report["Customer reference"])), None),
                reported_order_ref=next(iter(orders), None),
                related_order_refs=related,
                reported_issue=report["Reported issue"],
                reported_amount=Decimal(amount),
                reported_currency=currency,
                reported_at=source_time(report["Created"], "ticket_created"),
                payment_state=payment_state,
                field_provenance={
                    "primary_report_record_id": case.primary_report_record_id,
                    "identifier_provenance": report["Identifier provenance"],
                    "reported_order_source": report["Order reference"],
                    "reported_money_source": report["Reported amount/currency"],
                },
            )
        )
        for thread in case.thread_kinds:
            graph[CaseThread].append(
                dict(state_id=state_id, thread_kind=thread, case_id=case.case_id)
            )
        for record_id in case.evidence_record_ids:
            if record_id == case.primary_report_record_id:
                basis = AssociationBasis(
                    category="direct_ref_match",
                    matched_fields={"Ticket reference": report["Ticket reference"]},
                    explanation="The primary source complaint defines this application case, not a "
                    "verified payment outcome.",
                    basis_record_id=record_id,
                )
            else:
                relation = next(
                    r
                    for r in graph[EvidenceRelationship]
                    if r["to_record_id"] == record_id
                    and r["from_record_id"] in case.evidence_record_ids
                )
                basis = AssociationBasis.model_validate(
                    {
                        key: relation[key]
                        for key in ("category", "matched_fields", "explanation", "basis_record_id")
                    }
                )
            graph[CaseEvidenceLink].append(
                dict(
                    state_id=state_id,
                    case_id=case.case_id,
                    evidence_record_id=record_id,
                    **basis.model_dump(),
                )
            )
    return graph
