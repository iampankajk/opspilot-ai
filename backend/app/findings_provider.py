"""Offline adapter only. The protocol can later be implemented by an async OpenAI adapter."""

import json
from dataclasses import dataclass
from typing import Literal, Protocol

from app.findings_validation import returned_records


@dataclass(frozen=True)
class InputCount:
    input_tokens: int
    kind: str


@dataclass(frozen=True)
class ProviderResult:
    output_json: str
    status: Literal["completed", "refused", "incomplete"] = "completed"
    model: str = "mock-findings-v1"
    response_id: str | None = None
    usage: dict | None = None


class ProviderFailure(Exception):
    """Adapters translate provider exceptions to one of these safe categories."""

    def __init__(self, kind: Literal["configuration", "rate_limit", "unavailable"]):
        super().__init__(kind)
        self.kind = kind


class FindingsProvider(Protocol):
    name: str

    async def count_input(self, bundle: dict, *, timeout: float) -> InputCount: ...

    async def generate(self, bundle: dict, *, timeout: float) -> ProviderResult: ...


def citation(record, field, role="context"):
    return {
        "evidence_record_id": record,
        "pointer": "/payload/" + field.replace("~", "~0").replace("/", "~1"),
        "role": role,
        "explanation": "This retained field provides the stated evidence basis.",
    }


def finding(
    claim, status, citations, rationale, *, limitations=None, sources=None, hypothesis=False
):
    return {
        "kind": "hypothesis" if hypothesis else "observation",
        "claim": claim,
        "proposed_status": status,
        "citations": citations,
        "rationale": [
            {
                "text": rationale,
                "kind": "unverified_hypothesis" if hypothesis else "evidence_statement",
                "citation_indexes": list(range(len(citations))),
                "result_source_keys": sources or [],
            }
        ],
        "limitations": []
        if limitations is None
        else [
            {
                "text": limitations,
                "kind": "evidence_statement",
                "citation_indexes": list(range(len(citations))),
                "result_source_keys": sources or [],
            }
        ],
        "next_questions": [
            "What additional evidence would establish the provider and bank outcomes?"
        ],
    }


class MockFindingsProvider:
    """Fixed synthetic-scenario examples, not AI reasoning or a financial inference engine."""

    name = "mock"

    async def count_input(self, bundle: dict, *, timeout: float) -> InputCount:
        # Deterministic test units only; this is deliberately NOT an OpenAI token counter.
        units = (len(json.dumps(bundle, sort_keys=True).encode()) + 3) // 4
        return InputCount(max(1, units), "mock_estimate")

    async def generate(self, bundle: dict, *, timeout: float) -> ProviderResult:
        records = returned_records(bundle)
        proposals = []
        if "SYN-PO-ATT-001" in records:
            proposals.append(
                finding(
                    "The internal attempt recorded an unknown outcome after timeout.",
                    "confirmed",
                    [
                        citation("SYN-PO-ATT-001", f, "supports")
                        for f in ("Internal status", "Sanitized internal error")
                    ],
                    "The internal status and sanitized error record an unknown outcome "
                    "after a timeout.",
                )
            )
        if "SYN-STRIPE-FAIL-001" in records:
            proposals.append(
                finding(
                    "The available evidence establishes that this payment was never captured.",
                    "inconclusive",
                    [
                        citation("SYN-STRIPE-FAIL-001", f)
                        for f in (
                            "Capture event in this returned extract",
                            "Extract completeness",
                            "Settlement/bank posting evidence",
                        )
                    ],
                    "The incomplete returned extract cannot establish whether a capture occurred.",
                    limitations=(
                        "Provider completeness is unverified and bank/settlement evidence is "
                        "not constructed."
                    ),
                    hypothesis=True,
                )
            )
        if {"SYN-PO-ATT-002-A", "SYN-PO-ATT-002-B", "SYN-ZD-HANDOFF-001"} <= records.keys():
            refs = [
                citation(r, f, "supports")
                for r in ("SYN-PO-ATT-002-A", "SYN-PO-ATT-002-B")
                for f in ("Transaction / attempt", "Customer / order", "Amount/currency")
            ]
            refs += [
                citation("SYN-ZD-HANDOFF-001", f, "supports")
                for f in ("Candidate records returned", "Search result")
            ]
            proposals.append(
                finding(
                    "Two distinct internal attempt records share candidate customer/order "
                    "and amount context.",
                    "confirmed",
                    refs,
                    "The two internal attempts share the candidate context attributed to "
                    "the documented Support lookup.",
                )
            )
        if "SYN-STRIPE-DUP-001" in records:
            refs = [
                citation("SYN-STRIPE-DUP-001", f)
                for f in (
                    "Returned lifecycle events",
                    "Extract scope and completeness",
                    "Settlement/bank posting evidence",
                )
            ]
            proposals.append(
                finding(
                    "The returned provider extract contains two distinct capture references.",
                    "not_confirmed",
                    refs,
                    "The examined extract lists one capture reference; this does not "
                    "prove there was only one capture in reality.",
                )
            )
            bank_refs = list(refs)
            bank_rationale = (
                "The returned provider extract cannot establish the customer's bank "
                "posting outcome."
            )
            if "SYN-ZD-TICKET-002" in records:
                bank_refs.extend(
                    citation("SYN-ZD-TICKET-002", field)
                    for field in ("Reported issue", "Bank/issuer evidence")
                )
                bank_rationale += (
                    " The ticket records customer-reported symptoms; independent bank/issuer "
                    "verification is still missing."
                )
            for claim in (
                "The customer's bank posted two debits.",
                "The customer was charged only once.",
            ):
                proposals.append(
                    finding(
                        claim,
                        "inconclusive",
                        bank_refs,
                        bank_rationale,
                        limitations=(
                            "Provider completeness is unverified and bank/settlement evidence is "
                            "not constructed."
                        ),
                        hypothesis=True,
                    )
                )
        provider = next(
            s for s in bundle["evidence"]["source_outcomes"] if s["source_key"] == "stripe"
        )
        if provider["execution_status"] != "completed":
            proposals.append(
                finding(
                    "The available evidence establishes the customer's final payment outcome.",
                    "inconclusive",
                    [],
                    "The selected provider retrieval failed or was interrupted; its "
                    "outcome remains unknown.",
                    sources=["stripe"],
                    hypothesis=True,
                )
            )
        output = {
            "schema_version": "task5.v1",
            "findings": proposals,
            "no_findings_reason": None if proposals else "no_assessable_claims",
        }
        if (len(json.dumps(output).encode()) + 3) // 4 > bundle["response_options"][
            "max_output_tokens"
        ]:
            return ProviderResult(
                "", status="incomplete", usage={"input_tokens": 0, "output_tokens": 0}
            )
        return ProviderResult(json.dumps(output), usage={"input_tokens": 0, "output_tokens": 0})
