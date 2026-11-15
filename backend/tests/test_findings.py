# ruff: noqa: F811 -- pytest injects the imported shared fixture.
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_evidence import refresh, retrieve
from test_investigations import (
    HEADERS,
    bootstrap,
    context,  # noqa: F401
    create,
)

from app import findings
from app.findings_provider import MockFindingsProvider, ProviderFailure, ProviderResult
from app.main import create_app
from app.models import (
    AIGenerationRequest,
    AIProposal,
    AssessmentResultRef,
    EvidenceCitation,
    Finding,
    FindingCase,
    InvestigationState,
    WorkingDraft,
)


class ControlledProvider(MockFindingsProvider):
    def __init__(self, transform=None):
        self.transform = transform
        self.count_calls = self.generate_calls = 0

    async def count_input(self, bundle, *, timeout):
        self.count_calls += 1
        return await super().count_input(bundle, timeout=timeout)

    async def generate(self, bundle, *, timeout):
        self.generate_calls += 1
        result = await super().generate(bundle, timeout=timeout)
        if self.transform:
            return self.transform(result, bundle)
        return result


@pytest.fixture
def enabled(context):
    client, connection, app, clock, owner = context
    app.state.settings = app.state.settings.model_copy(update={"ai_findings_enabled": True})
    app.state.findings_provider = ControlledProvider()
    return client, connection, app, clock, owner


def endpoint(
    workspace, thread="payment_failures", case="case-failure-001", action="finding-generations"
):
    return (
        f"/api/v1/investigations/{workspace['investigation_id']}/threads/{thread}"
        f"/cases/{case}/{action}"
    )


def prepare(client, thread="payment_failures", case="case-failure-001"):
    workspace = create(client).json()
    evidence = retrieve(client, workspace, thread, case)
    assert evidence.status_code == 200, evidence.text
    return workspace | {
        "draft_version": evidence.json()["draft_version"],
        "evidence_request_id": evidence.json()["evidence_request_id"],
    }


def generate(client, workspace, thread="payment_failures", case="case-failure-001", **overrides):
    return client.post(
        endpoint(workspace, thread, case),
        headers=HEADERS,
        json={
            "state_id": workspace["state_id"],
            "expected_draft_version": workspace["draft_version"],
            "evidence_request_id": workspace["evidence_request_id"],
        }
        | overrides,
    )


def read(client, workspace, thread="payment_failures", case="case-failure-001"):
    return client.get(
        endpoint(workspace, thread, case, "findings"), params={"state_id": workspace["state_id"]}
    )


def attempts(connection, workspace):
    with Session(bind=connection) as db:
        return db.scalars(
            select(AIGenerationRequest)
            .where(
                AIGenerationRequest.state_id == UUID(workspace["state_id"]),
            )
            .order_by(AIGenerationRequest.expected_draft_version)
        ).all()


def graph_counts(connection, workspace):
    with Session(bind=connection) as db:
        return [
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.state_id == UUID(workspace["state_id"]),
                )
            )
            for model in (Finding, FindingCase, AIProposal, EvidenceCitation, AssessmentResultRef)
        ]


@pytest.mark.parametrize(
    "thread,case,count",
    [
        ("payment_failures", "case-failure-001", 2),
        ("possible_duplicates", "case-duplicate-001", 4),
    ],
)
def test_success_and_durable_read_without_another_provider_call(enabled, thread, case, count):
    client, connection, app, _, _ = enabled
    workspace = prepare(client, thread, case)
    before = read(client, workspace, thread, case)
    assert before.status_code == 200 and before.json()["generation_status"] == "not_started"
    response = generate(client, workspace, thread, case)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["generation_status"] == "completed" and body["draft_version"] == 4
    assert len(body["findings"]) == count
    assert len(body["source_outcomes"]) == 6
    assert all(f["review_state"] == "awaiting_review" for f in body["findings"])
    assert all("human_reviewed_status" not in f for f in body["findings"])
    assert response.headers["cache-control"] == "no-store"
    assert body["request_id"] == response.headers["x-request-id"]
    assert app.state.findings_provider.generate_calls == 1
    restored = read(client, workspace, thread, case).json()
    assert restored["findings"] == body["findings"]
    assert restored["cited_records"] == body["cited_records"]
    assert app.state.findings_provider.generate_calls == 1
    operation = attempts(connection, workspace)[0]
    assert operation.status == "completed" and operation.provider == "mock"
    assert operation.actual_cost_usd == 0 and operation.usage["input_tokens"] == 0
    assert operation.input_bundle["response_options"]["tools"] == []
    assert operation.input_bundle["response_options"]["prompt_cache_options"] == {
        "mode": "explicit"
    }
    assert "field_provenance" in body["cited_records"][0]
    assert graph_counts(connection, workspace)[:3] == [count] * 3
    again = generate(client, workspace | {"draft_version": 4}, thread, case)
    assert (
        again.status_code == 409 and again.json()["error"]["code"] == "FINDINGS_ALREADY_GENERATED"
    )
    assert len(attempts(connection, workspace)) == 1


def test_valid_empty_result_consumes_initial_generation_slot(enabled):
    client, connection, app, _, _ = enabled
    app.state.findings_provider = ControlledProvider(
        lambda *_: ProviderResult(
            json.dumps(
                {
                    "schema_version": "task5.v1",
                    "findings": [],
                    "no_findings_reason": "no_assessable_claims",
                }
            )
        )
    )
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 201, response.text
    assert response.json()["findings"] == []
    assert read(client, workspace).json()["no_findings_reason"] == "no_assessable_claims"
    assert generate(client, workspace | {"draft_version": 4}).status_code == 409
    assert graph_counts(connection, workspace) == [0] * 5


def output_transform(mutate):
    def transform(result, _):
        output = json.loads(result.output_json)
        mutate(output)
        return ProviderResult(json.dumps(output))

    return transform


@pytest.mark.parametrize(
    "mutation", ["json", "extra", "empty_reason", "status", "bool_index", "blank", "too_many"]
)
def test_malformed_output_fails_atomically_and_retains_safe_history(enabled, mutation):
    client, connection, app, _, _ = enabled

    def mutate(out):
        item = out["findings"][0]
        if mutation == "extra":
            item["human_reviewed_status"] = "confirmed"
        elif mutation == "empty_reason":
            out["no_findings_reason"] = "no_assessable_claims"
        elif mutation == "status":
            item["proposed_status"] = "approved"
        elif mutation == "bool_index":
            item["rationale"][0]["citation_indexes"] = [True]
        elif mutation == "blank":
            item["claim"] = "   "
        elif mutation == "too_many":
            out["findings"] *= 4

    transform = (
        (lambda *_: ProviderResult("not JSON PRIVATE_PROVIDER_ERROR"))
        if mutation == "json"
        else output_transform(mutate)
    )
    app.state.findings_provider = ControlledProvider(transform)
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == 502, result.text
    assert result.json()["error"]["code"] == "AI_OUTPUT_INVALID"
    assert "PRIVATE_PROVIDER_ERROR" not in result.text
    operation = attempts(connection, workspace)[0]
    assert operation.status == "failed" and operation.normalized_output is None
    assert graph_counts(connection, workspace) == [0] * 5
    assert read(client, workspace).json()["generation_status"] == "failed"


@pytest.mark.parametrize(
    "mutation",
    [
        "invented",
        "unreturned",
        "wrong_case",
        "pointer",
        "escape",
        "index",
        "duplicate",
        "unsupported",
        "duplicate_claim",
    ],
)
def test_invalid_citation_or_basis_rejects_whole_output(enabled, mutation):
    client, connection, app, _, _ = enabled

    def mutate(out):
        item = out["findings"][0]
        c = item["citations"][0]
        if mutation == "invented":
            c["evidence_record_id"] = "SYN-INVENTED"
        elif mutation == "unreturned":
            c["evidence_record_id"] = "SYN-PD-ALERT-001"
        elif mutation == "wrong_case":
            c["evidence_record_id"] = "SYN-PO-ATT-002-A"
        elif mutation == "pointer":
            c["pointer"] = "/payload/not constructed"
        elif mutation == "escape":
            c["pointer"] = "/payload/Invalid~2escape"
        elif mutation == "index":
            item["rationale"][0]["citation_indexes"] = [7]
        elif mutation == "duplicate":
            item["citations"].append(deepcopy(c))
        elif mutation == "unsupported":
            for citation in item["citations"]:
                citation["role"] = "context"
        elif mutation == "duplicate_claim":
            out["findings"].append(deepcopy(item))

    app.state.findings_provider = ControlledProvider(output_transform(mutate))
    workspace = prepare(client)
    response = generate(client, workspace)
    assert (
        response.status_code == 502 and response.json()["error"]["code"] == "AI_REFERENCE_INVALID"
    ), response.text
    assert graph_counts(connection, workspace) == [0] * 5


def test_failed_attempt_retry_appends_without_rewriting_prior_history(enabled):
    client, connection, app, _, _ = enabled
    app.state.findings_provider = ControlledProvider(lambda *_: ProviderResult("invalid"))
    workspace = prepare(client)
    first = generate(client, workspace)
    first_id = first.json()["error"]["details"]["generation_id"]
    original = attempts(connection, workspace)[0]
    app.state.findings_provider = ControlledProvider()
    workspace["draft_version"] = refresh(client, workspace)["draft_version"]
    retry = generate(client, workspace, retry_of_generation_id=first_id)
    assert retry.status_code == 201, retry.text
    rows = attempts(connection, workspace)
    assert len(rows) == 2 and rows[0].status == "failed" and rows[1].status == "completed"
    assert rows[0].input_bundle == original.input_bundle
    assert str(rows[1].retry_of_generation_id) == first_id
    assert retry.json()["draft_version"] == 6


def test_publication_rollback_retains_pending_attempt_but_no_findings(enabled, monkeypatch):
    client, connection, _, clock, _ = enabled
    workspace = prepare(client)
    original = findings.publish

    def fail(*args):
        original(*args)
        raise IntegrityError("injected", {}, Exception())

    monkeypatch.setattr(findings, "publish", fail)
    response = generate(client, workspace)
    assert response.status_code == 503
    assert attempts(connection, workspace)[0].status == "pending"
    assert graph_counts(connection, workspace) == [0] * 5
    clock.now += timedelta(seconds=21)
    restored = read(client, workspace)
    assert restored.status_code == 200 and restored.json()["generation_status"] == "interrupted"
    assert restored.json()["draft_version"] == 4


@pytest.mark.parametrize("change", ["version", "state", "expiry"])
def test_late_results_never_attach_to_changed_context(enabled, change):
    client, connection, app, clock, _ = enabled
    workspace = prepare(client)

    def changed(result, _):
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
            draft = db.get(WorkingDraft, UUID(workspace["investigation_id"]))
            if change == "version":
                draft.draft_version += 1
            elif change == "expiry":
                clock.now += timedelta(hours=24)
            else:
                old = db.get(InvestigationState, draft.state_id)
                replacement = InvestigationState(
                    investigation_id=old.investigation_id,
                    dataset_version_id=old.dataset_version_id,
                    incident_context=old.incident_context,
                    limitations=old.limitations,
                )
                db.add(replacement)
                db.flush()
                draft.state_id = replacement.state_id
        return result

    app.state.findings_provider = ControlledProvider(changed)
    response = generate(client, workspace)
    assert response.status_code == (401 if change == "expiry" else 409), response.text
    assert graph_counts(connection, workspace) == [0] * 5
    assert attempts(connection, workspace)[0].status == (
        "stale" if change == "version" else "pending"
    )


def test_authorization_scope_and_request_guards_create_no_attempts(enabled):
    client, connection, app, _, _ = enabled
    workspace = prepare(client)
    path = endpoint(workspace)
    body = {
        "state_id": workspace["state_id"],
        "expected_draft_version": workspace["draft_version"],
        "evidence_request_id": workspace["evidence_request_id"],
    }
    for overrides in (
        {"expected_draft_version": -1},
        {"expected_draft_version": True},
        {"model": "caller-selected"},
        {"sql": "SELECT anything"},
    ):
        assert client.post(path, headers=HEADERS, json=body | overrides).status_code == 422
    assert client.post(path + "?override=1", headers=HEADERS, json=body).status_code == 422
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, headers=HEADERS, content="not json").status_code == 415
    assert (
        client.post(
            path, headers=HEADERS | {"Content-Type": "application/json"}, content=" " * 4097
        ).status_code
        == 413
    )
    assert generate(client, workspace, state_id=str(uuid4())).status_code == 409
    assert generate(client, workspace, evidence_request_id=str(uuid4())).status_code == 404
    assert generate(client, workspace, retry_of_generation_id=str(uuid4())).status_code == 404
    assert generate(client, workspace, thread="possible_duplicates").status_code == 404
    bad_query = (
        endpoint(workspace, action="findings") + f"?state_id={workspace['state_id']}&extra=1"
    )
    assert client.get(bad_query).status_code == 422
    with TestClient(create_app(app.state.settings), base_url="https://localhost:3000") as other:
        assert generate(other, workspace).status_code == 401
        bootstrap(other)
        assert generate(other, workspace).status_code == 404
        assert read(other, workspace).status_code == 404
    assert attempts(connection, workspace) == []
    assert app.state.findings_provider.generate_calls == 0


@pytest.mark.parametrize(
    "setting,value,code",
    [
        ("ai_findings_enabled", False, "AI_NOT_CONFIGURED"),
        ("ai_findings_provider", "openai", "AI_CONFIGURATION_ERROR"),
        ("ai_findings_model", "unreviewed-model", "AI_CONFIGURATION_ERROR"),
    ],
)
def test_configuration_fails_closed_without_credentials_or_calls(enabled, setting, value, code):
    client, connection, app, _, _ = enabled
    workspace = prepare(client)
    app.state.settings = app.state.settings.model_copy(update={setting: value})
    result = generate(client, workspace)
    assert result.status_code == 503 and result.json()["error"]["code"] == code
    assert result.json()["error"]["retryable"] is False
    assert attempts(connection, workspace) == []


@pytest.mark.parametrize(
    "failure,status,code,retryable",
    [
        ("refused", 422, "AI_REFUSED", False),
        ("incomplete", 502, "AI_OUTPUT_INCOMPLETE", True),
        ("rate_limit", 503, "AI_PROVIDER_RATE_LIMITED", True),
        ("configuration", 503, "AI_CONFIGURATION_ERROR", False),
        ("unavailable", 503, "AI_PROVIDER_UNAVAILABLE", True),
    ],
)
def test_provider_failures_have_safe_terminal_history(enabled, failure, status, code, retryable):
    client, connection, app, _, _ = enabled

    def transform(result, bundle):
        if failure in {"refused", "incomplete"}:
            return ProviderResult("PRIVATE_OUTPUT", status=failure)
        raise ProviderFailure(failure)

    app.state.findings_provider = ControlledProvider(transform)
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == status and result.json()["error"]["code"] == code, result.text
    assert result.json()["error"]["retryable"] is retryable
    assert "PRIVATE_OUTPUT" not in result.text
    assert attempts(connection, workspace)[0].status == "failed"
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize("stage", ["count_input", "generate"])
def test_real_async_timeout_cancels_provider_and_leaves_retryable_history(enabled, stage):
    client, connection, app, _, _ = enabled
    cancelled = []

    async def slow(*_, **__):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)

    setattr(app.state.findings_provider, stage, slow)
    field = (
        "ai_findings_count_timeout_seconds"
        if stage == "count_input"
        else "ai_findings_model_timeout_seconds"
    )
    app.state.settings = app.state.settings.model_copy(update={field: 0.03})
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == 503 and result.json()["error"]["code"] == "AI_DEADLINE_EXCEEDED"
    assert cancelled == [True]
    operation = attempts(connection, workspace)[0]
    assert operation.status == "interrupted" and operation.actual_cost_usd is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "limit,code",
    [
        ("ai_findings_max_input_tokens", "AI_INPUT_LIMIT"),
        ("ai_findings_max_attempt_usd", "AI_BUDGET_EXCEEDED"),
        ("ai_findings_max_output_tokens", "AI_OUTPUT_INCOMPLETE"),
    ],
)
def test_configured_limits_are_admission_bounds_not_billing_caps(enabled, limit, code):
    client, connection, app, _, _ = enabled
    value = 1 if limit != "ai_findings_max_attempt_usd" else "0.000001"
    if limit == "ai_findings_max_attempt_usd":
        from decimal import Decimal

        value = Decimal(value)
    app.state.settings = app.state.settings.model_copy(update={limit: value})
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.json()["error"]["code"] == code, result.text
    assert graph_counts(connection, workspace) == [0] * 5
    assert app.state.findings_provider.generate_calls == (
        1 if code == "AI_OUTPUT_INCOMPLETE" else 0
    )


def test_attempt_allowance_counts_failures_and_does_not_reset_on_retry(enabled):
    client, connection, app, _, _ = enabled
    app.state.settings = app.state.settings.model_copy(
        update={"ai_findings_max_attempts_per_case": 2}
    )
    app.state.findings_provider = ControlledProvider(lambda *_: ProviderResult("invalid"))
    workspace = prepare(client)
    for _ in range(2):
        assert generate(client, workspace).status_code == 502
        workspace["draft_version"] = refresh(client, workspace)["draft_version"]
    exhausted = generate(client, workspace)
    assert exhausted.status_code == 429 and exhausted.json()["error"]["code"] == "AI_ATTEMPT_LIMIT"
    assert len(attempts(connection, workspace)) == 2


def test_reconciliation_commits_before_a_rejected_stale_retry(enabled, monkeypatch):
    client, connection, _, clock, _ = enabled
    workspace = prepare(client)

    def crash(*args):
        raise RuntimeError("test process interruption")

    monkeypatch.setattr(findings, "reserve", crash)
    assert generate(client, workspace).status_code == 500
    operation = attempts(connection, workspace)[0]
    assert operation.status == "pending"
    assert (
        generate(client, workspace | {"draft_version": 3}).json()["error"]["code"]
        == "OPERATION_IN_PROGRESS"
    )
    clock.now += timedelta(seconds=21)
    rejected = generate(client, workspace, retry_of_generation_id=str(operation.generation_id))
    assert rejected.status_code == 409
    assert attempts(connection, workspace)[0].status == "interrupted"
    assert refresh(client, workspace)["draft_version"] == 4


def test_failed_start_and_reservation_roll_back_without_model_execution(enabled, monkeypatch):
    client, connection, app, _, _ = enabled
    workspace = prepare(client)

    def fail(*args):
        raise IntegrityError("injected", {}, Exception())

    with monkeypatch.context() as patch:
        patch.setattr(findings, "advance", fail)
        assert generate(client, workspace).status_code == 503
    assert attempts(connection, workspace) == []
    with monkeypatch.context() as patch:
        patch.setattr(findings, "reserve", fail)
        assert generate(client, workspace).status_code == 503
    assert attempts(connection, workspace)[0].status == "pending"
    assert app.state.findings_provider.generate_calls == 0


@pytest.mark.parametrize("pending_kind", ["generation", "evidence"])
def test_cross_connection_evidence_and_generation_exclude_each_other(
    database, monkeypatch, pending_kind
):
    from app import evidence

    _, settings = database
    settings = settings.model_copy(update={"ai_findings_enabled": True})
    entered, release = Event(), Event()

    class PausedProvider(ControlledProvider):
        async def generate(self, bundle, *, timeout):
            entered.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
            return await super().generate(bundle, timeout=timeout)

    original = evidence.collect

    def paused_evidence(*args):
        entered.set()
        assert release.wait(8)
        return original(*args)

    with (
        TestClient(create_app(settings), base_url="https://localhost:3000") as first,
        TestClient(create_app(settings), base_url="https://localhost:3000") as second,
    ):
        bootstrap(first)
        workspace = prepare(first)
        second.cookies.update(first.cookies)
        if pending_kind == "generation":
            first.app.state.findings_provider = PausedProvider()
        else:
            monkeypatch.setattr(evidence, "collect", paused_evidence)
        operation = generate if pending_kind == "generation" else retrieve
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(operation, first, workspace)
            assert entered.wait(8)
            try:
                current = workspace | {"draft_version": 3}
                denied = generate(second, current)
                assert (
                    denied.status_code == 409
                    and denied.json()["error"]["code"] == "OPERATION_IN_PROGRESS"
                )
                denied_evidence = retrieve(second, current)
                assert (
                    denied_evidence.status_code == 409
                    and denied_evidence.json()["error"]["code"] == "OPERATION_IN_PROGRESS"
                )
            finally:
                release.set()
            assert future.result(timeout=15).status_code == (
                201 if pending_kind == "generation" else 200
            )


@pytest.mark.parametrize(
    "mutation",
    [
        "pointer_owner",
        "returned_membership",
        "source",
        "thread",
        "status",
        "ordinal",
        "success_slot",
    ],
)
def test_database_constraints_protect_persisted_scope(enabled, mutation):
    client, connection, _, _, _ = enabled
    workspace = prepare(client)
    assert generate(client, workspace).status_code == 201
    state = UUID(workspace["state_id"])
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        with pytest.raises(IntegrityError) as error, db.begin_nested():
            citation_row = db.scalar(
                select(EvidenceCitation).where(EvidenceCitation.state_id == state)
            )
            if mutation == "returned_membership":
                citation_row.evidence_record_id = "SYN-PD-ALERT-001"
            elif mutation == "source":
                citation_row.source_key = (
                    "internal_payments" if citation_row.source_key == "stripe" else "stripe"
                )
            elif mutation == "ordinal":
                citation_row.ordinal = 8
            elif mutation == "status":
                proposal = db.get(AIProposal, (state, citation_row.proposal_id))
                proposal.proposed_status = "reviewed"
            elif mutation == "thread":
                link = db.scalar(select(FindingCase).where(FindingCase.state_id == state))
                link.thread_kind = "possible_duplicates"
            elif mutation == "pointer_owner":
                rows = db.scalars(select(Finding).where(Finding.state_id == state)).all()
                rows[0].current_proposal_id = rows[1].current_proposal_id
            elif mutation == "success_slot":
                prior = db.scalar(
                    select(AIGenerationRequest).where(AIGenerationRequest.state_id == state)
                )
                values = {
                    column.name: getattr(prior, column.name) for column in prior.__table__.columns
                }
                values["generation_id"] = uuid4()
                db.add(AIGenerationRequest(**values))
            db.flush()
        if mutation == "source":
            assert error.value.orig.sqlstate == "23503"
            assert (
                error.value.orig.diag.constraint_name
                == "fk_evidence_citations_state_id_retrieval_result_records"
            )


@pytest.mark.parametrize("corruption", ["count", "missing_source", "source_status"])
def test_inconsistent_selected_source_outcomes_cannot_reach_provider(enabled, corruption):
    from app.models import RetrievalResult

    client, connection, app, _, _ = enabled
    workspace = prepare(client)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        row = db.get(
            RetrievalResult,
            (UUID(workspace["state_id"]), UUID(workspace["evidence_request_id"]), "stripe"),
        )
        if corruption == "count":
            row.returned_count = 2
        elif corruption == "missing_source":
            row = db.get(
                RetrievalResult,
                (
                    UUID(workspace["state_id"]),
                    UUID(workspace["evidence_request_id"]),
                    "support_lookup",
                ),
            )
            db.delete(row)
        else:
            row.availability = "not_constructed"
    response = generate(client, workspace)
    assert (
        response.status_code == 503 and response.json()["error"]["code"] == "AI_EVIDENCE_INVALID"
    ), response.text
    assert attempts(connection, workspace) == []
    assert app.state.findings_provider.generate_calls == 0


def test_preflight_failure_retains_unknown_usage_and_never_generates(enabled):
    client, connection, app, _, _ = enabled

    async def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_ERROR_DO_NOT_EXPOSE")

    app.state.findings_provider.count_input = fail
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 503 and response.json()["error"]["code"] == "AI_PREFLIGHT_FAILED"
    assert "PRIVATE_ERROR" not in response.text
    assert attempts(connection, workspace)[0].usage is None
    assert app.state.findings_provider.generate_calls == 0


def test_older_terminal_evidence_request_remains_a_valid_exact_input(enabled):
    client, _, _, _, _ = enabled
    workspace = prepare(client)
    selected = workspace["evidence_request_id"]
    newer = retrieve(client, workspace)
    assert newer.status_code == 200
    workspace["draft_version"] = newer.json()["draft_version"]
    response = generate(client, workspace)
    assert response.status_code == 201
    assert response.json()["generation_history"][0]["evidence_request_id"] == selected


@pytest.mark.parametrize("status", ["failed", "interrupted", "stale"])
def test_noneligible_evidence_history_cannot_seed_findings(enabled, status):
    from app.models import EvidenceRequest

    client, connection, _, _, _ = enabled
    workspace = prepare(client)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        operation = db.get(
            EvidenceRequest, (UUID(workspace["state_id"]), UUID(workspace["evidence_request_id"]))
        )
        operation.status = status
    response = generate(client, workspace)
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "INVALID_EVIDENCE_REQUEST"
    )
    assert attempts(connection, workspace) == []


def test_retry_reference_must_match_selected_request_and_be_retryable(enabled):
    client, connection, app, _, _ = enabled
    app.state.findings_provider = ControlledProvider(lambda *_: ProviderResult("invalid"))
    workspace = prepare(client)
    failure = generate(client, workspace)
    generation_id = failure.json()["error"]["details"]["generation_id"]
    current = workspace | {"draft_version": refresh(client, workspace)["draft_version"]}
    inspected = retrieve(client, current)
    current |= {
        "draft_version": inspected.json()["draft_version"],
        "evidence_request_id": inspected.json()["evidence_request_id"],
    }
    rejected = generate(client, current, retry_of_generation_id=generation_id)
    assert (
        rejected.status_code == 409
        and rejected.json()["error"]["code"] == "INVALID_RETRY_REFERENCE"
    )
    assert len(attempts(connection, workspace)) == 1
    # A genuinely fresh initial attempt may select this newer request without rewriting history.
    app.state.findings_provider = ControlledProvider()
    assert generate(client, current).status_code == 201


def test_duplicate_json_keys_are_not_silently_accepted(enabled):
    client, connection, app, _, _ = enabled
    app.state.findings_provider = ControlledProvider(
        lambda *_: ProviderResult(
            '{"schema_version":"bad","schema_version":"task5.v1","findings":[],"no_findings_reason":"no_assessable_claims"}'
        )
    )
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 502 and response.json()["error"]["code"] == "AI_OUTPUT_INVALID"
    assert graph_counts(connection, workspace) == [0] * 5


def test_findings_survive_real_https_process_restart_without_enabled_provider(database):
    import os
    import socket
    import ssl
    import subprocess
    import sys
    from pathlib import Path
    from time import monotonic, sleep

    import httpx

    _, settings = database
    root = Path(__file__).resolve().parents[2]
    cert, key = root / ".certs/localhost.pem", root / ".certs/localhost-key.pem"
    assert cert.is_file() and key.is_file()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    environment |= {
        "DATABASE_URL": settings.database_url.get_secret_value(),
        "AI_FINDINGS_ENABLED": "true",
        "AI_FINDINGS_PROVIDER": "mock",
    }
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
        "--log-level",
        "critical",
        "--ssl-certfile",
        str(cert),
        "--ssl-keyfile",
        str(key),
    ]
    base = f"https://localhost:{port}"
    tls = ssl.create_default_context(cafile=str(cert))

    def stop(process):
        process.terminate()
        process.wait(timeout=5)

    def launch():
        process = subprocess.Popen(
            args,
            cwd=root / "backend",
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = monotonic() + 8
        while monotonic() < deadline:
            try:
                with httpx.Client(base_url=base, verify=tls, trust_env=False) as probe:
                    if probe.get("/api/v1/health").status_code == 200:
                        return process
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                break
            sleep(0.05)
        stop(process)
        pytest.fail("Temporary mock-only HTTPS backend did not become ready")

    process = launch()
    try:
        with httpx.Client(base_url=base, verify=tls, trust_env=False) as client:
            bootstrap(client)
            workspace = prepare(client)
            response = generate(client, workspace)
            assert response.status_code == 201, response.text
            expected = response.json()
            jar = client.cookies
    finally:
        stop(process)
    environment["AI_FINDINGS_ENABLED"] = "false"
    process = launch()
    try:
        with httpx.Client(base_url=base, verify=tls, trust_env=False) as client:
            client.cookies.update(jar)
            stored = read(client, workspace)
            assert stored.status_code == 200
            for field in (
                "state_id",
                "draft_version",
                "findings",
                "cited_records",
                "source_outcomes",
                "relationships",
                "generation_history",
            ):
                assert stored.json()[field] == expected[field]
            assert stored.json()["generation_status"] == "completed"
    finally:
        stop(process)
