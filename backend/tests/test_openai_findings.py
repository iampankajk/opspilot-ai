"""Exercise the pinned SDK, FastAPI workflow, and PostgreSQL with a fake HTTP transport."""

import asyncio
import json
import logging
from datetime import timedelta
from decimal import Decimal
from threading import Event

import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session
from test_findings import attempts, generate, graph_counts, prepare, read
from test_investigations import (
    bootstrap,
    context,  # noqa: F401
)

from app import findings, openai_findings_provider
from app.config import Settings
from app.findings import INSTRUCTIONS
from app.findings_schemas import FindingGenerationOutput
from app.main import create_app
from app.models import AIGenerationRequest

COUNT = "/v1/responses/input_tokens"
CREATE = "/v1/responses"
FAKE_KEY = "offline-transport-placeholder"
PRIVATE = "private-provider-test-marker"
MODEL = "gpt-6-luna"
RESPONSE_ID = "resp_offline_test"
REJECTED_MODEL = "sk-offline-model-only-marker"


def cited_output():
    return {
        "schema_version": "task5.v1",
        "no_findings_reason": None,
        "findings": [
            {
                "kind": "observation",
                "claim": "The internal attempt recorded an unknown outcome.",
                "proposed_status": "confirmed",
                "citations": [
                    {
                        "evidence_record_id": "SYN-PO-ATT-001",
                        "pointer": "/payload/Internal status",
                        "role": "supports",
                        "explanation": "The internal status reports the observed outcome.",
                    }
                ],
                "rationale": [
                    {
                        "text": "The internal attempt status is the basis for the observation.",
                        "kind": "evidence_statement",
                        "citation_indexes": [0],
                        "result_source_keys": [],
                    }
                ],
                "limitations": [],
                "next_questions": [],
            }
        ],
    }


def provider_response(*, parts=None, **overrides):
    if parts is None:
        parts = [{"type": "output_text", "text": json.dumps(cited_output()), "annotations": []}]
    return {
        "object": "response",
        "id": RESPONSE_ID,
        "model": MODEL,
        "status": "completed",
        "service_tier": "default",
        "output": [
            {
                "type": "message",
                "id": "msg_offline_test",
                "role": "assistant",
                "status": "completed",
                "content": parts,
            }
        ],
        "usage": {
            "input_tokens": 6000,
            "output_tokens": 1500,
            "total_tokens": 7500,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0, "ignored": PRIVATE},
            "ignored": PRIVATE,
        },
        **overrides,
    }


@pytest.fixture
def fake_sdk(monkeypatch):
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    received = []
    clients = []
    handlers = {
        COUNT: lambda _: httpx2.Response(
            200,
            content=b'{"object":"response.input_tokens","input_tokens":6000}',
            headers={"content-type": "application/json"},
        ),
        CREATE: lambda _: httpx2.Response(200, json=provider_response()),
    }

    def dispatch(request):
        assert request.method == "POST"
        assert request.url.scheme == "https" and request.url.host == "api.openai.com"
        assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
        assert "cookie" not in request.headers
        received.append(request)
        return handlers[request.url.path](request)

    original = openai_findings_provider.DefaultAsyncHttpx2Client

    def fake_client(**options):
        assert options["trust_env"] is False and options["follow_redirects"] is False
        client = original(transport=httpx2.MockTransport(dispatch), **options)
        clients.append(client)
        return client

    monkeypatch.setattr(openai_findings_provider, "DefaultAsyncHttpx2Client", fake_client)
    yield received, handlers
    assert clients and all(client.is_closed and not client.cookies for client in clients)


@pytest.fixture
def openai_context(fake_sdk, monkeypatch, request):
    def create_with_openai(settings):
        return create_app(
            settings.model_copy(
                update={
                    "ai_findings_enabled": True,
                    "ai_findings_provider": "openai",
                    "openai_api_key": SecretStr(FAKE_KEY),
                }
            )
        )

    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr("test_investigations.create_app", create_with_openai)
    return request.getfixturevalue("context")


def test_sdk_serialization_reservation_and_durable_publication(openai_context, fake_sdk, caplog):
    client, connection, app, _, _ = openai_context
    received, handlers = fake_sdk
    workspace = prepare(client)
    create_response = handlers[CREATE]

    def confirm_reservation(request):
        (row,) = attempts(connection, workspace)
        assert row.status == "pending" and row.counted_input_tokens == 6000
        assert row.reserved_cost_usd == Decimal("0.0021")
        return create_response(request)

    handlers[CREATE] = confirm_reservation
    assert app.state.findings_provider.client.max_retries == 0
    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)
    assert result.status_code == 201, result.text
    assert [item.url.path for item in received] == [COUNT, CREATE]
    count, generation = (json.loads(request.content) for request in received)
    (row,) = attempts(connection, workspace)

    data = json.dumps(
        {key: row.input_bundle[key] for key in ("context", "evidence")}, sort_keys=True
    )
    schema = count["text"]["format"]["schema"]
    app_schema = FindingGenerationOutput.model_json_schema()
    assert app_schema["$defs"]["FindingDraft"]["properties"]["claim"]["maxLength"] == 240
    assert '"maxLength"' not in json.dumps(schema) and '"minLength"' not in json.dumps(schema)
    for object_schema in [schema, *schema["$defs"].values()]:
        assert object_schema["additionalProperties"] is False
        assert set(object_schema["required"]) == set(object_schema["properties"])
    assert count == {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "input": [{"role": "user", "content": f"Selected synthetic case evidence (JSON):\n{data}"}],
        "reasoning": {"effort": "none"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "opspilot_findings_v1",
                "strict": True,
                "schema": schema,
            }
        },
        "tools": [],
        "truncation": "disabled",
    }
    assert generation == count | {
        "background": False,
        "max_output_tokens": 3000,
        "prompt_cache_options": {"mode": "explicit"},
        "service_tier": "default",
        "store": False,
        "stream": False,
    }
    for request, timeout in zip(received, (3.0, 10.0), strict=True):
        assert 0 < request.extensions["timeout"]["read"] <= timeout
    assert row.provider == "openai" and row.configured_model == row.returned_model == MODEL
    assert row.provider_response_id == RESPONSE_ID
    assert row.budget["token_count_kind"] == "openai_input_tokens"
    assert row.actual_cost_usd == Decimal("0.00135")
    assert row.usage == {
        "input_tokens": 6000,
        "output_tokens": 1500,
        "total_tokens": 7500,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
    }
    for value in (FAKE_KEY, PRIVATE, INSTRUCTIONS, "SYN-PO-ATT-001", RESPONSE_ID):
        assert value not in caplog.text
    assert PRIVATE not in result.text and RESPONSE_ID not in result.text
    stored_response = read(client, workspace)
    assert stored_response.status_code == 200
    for key in ("findings", "cited_records", "generation_history"):
        assert stored_response.json()[key] == result.json()[key]
    assert result.json()["findings"][0]["review_state"] == "awaiting_review"
    assert graph_counts(connection, workspace) == [1, 1, 1, 1, 0]
    assert len(received) == 2


@pytest.mark.parametrize(
    "stage,upstream_status,code,retryable",
    [
        (COUNT, 401, "AI_CONFIGURATION_ERROR", False),
        (COUNT, 429, "AI_PROVIDER_RATE_LIMITED", True),
        (COUNT, 500, "AI_PROVIDER_UNAVAILABLE", True),
        (CREATE, 400, "AI_CONFIGURATION_ERROR", False),
        (CREATE, 403, "AI_CONFIGURATION_ERROR", False),
        (CREATE, 429, "AI_PROVIDER_RATE_LIMITED", True),
        (CREATE, 503, "AI_PROVIDER_UNAVAILABLE", True),
    ],
)
def test_sdk_http_error_is_safe_and_never_retried(
    openai_context, fake_sdk, caplog, stage, upstream_status, code, retryable
):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    handlers[stage] = lambda _: httpx2.Response(
        upstream_status, headers={"x-should-retry": "true"}, json={"error": {"message": PRIVATE}}
    )
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == 503 and result.json()["error"]["code"] == code
    assert result.json()["error"]["retryable"] is retryable
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
    assert [item.url.path for item in received] == ([COUNT] if stage == COUNT else [COUNT, CREATE])
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.usage is None and row.actual_cost_usd is None
    assert (row.reserved_cost_usd is not None) == (stage == CREATE)
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "tokens,max_attempt_usd,status,code",
    [
        (True, "0.003", 503, "AI_PREFLIGHT_FAILED"),
        (12001, "0.003", 422, "AI_INPUT_LIMIT"),
        (6000, "0.002", 422, "AI_BUDGET_EXCEEDED"),
    ],
)
def test_sdk_count_stops_generation_before_admission(
    openai_context, fake_sdk, tokens, max_attempt_usd, status, code
):
    client, connection, app, _, _ = openai_context
    received, handlers = fake_sdk
    app.state.settings = app.state.settings.model_copy(
        update={"ai_findings_max_attempt_usd": Decimal(max_attempt_usd)}
    )
    handlers[COUNT] = lambda _: httpx2.Response(
        200, json={"object": "response.input_tokens", "input_tokens": tokens}
    )
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == status and result.json()["error"]["code"] == code
    assert [item.url.path for item in received] == [COUNT]
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.reserved_cost_usd is None and row.usage is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "body",
    [
        b'{"object":"response.input_tokens","input_tokens":15001,"input_tokens":6000}',
        b'{"object":"response","object":"response.input_tokens","input_tokens":6000}',
        b'{"object":"response.input_tokens","input_tokens":6000,'
        b'"metadata":[{"marker":"private-provider-test-marker","marker":0}]}',
        b'{"object":"response.input_tokens","input_tokens":true}',
        b'{"object":"response.input_tokens","input_tokens":-1}',
        b'{"object":"response.input_tokens","input_tokens":6000.0}',
        b'{"object":"response.input_tokens","input_tokens":"6000"}',
        b'{"object":"response.input_tokens","input_tokens":null}',
        b'{"object":"response.input_tokens","input_tokens":{"value":6000}}',
        b'{"object":"response.input_tokens"}',
        b'{"input_tokens":6000}',
        b'{"object":"response","input_tokens":6000}',
        b'[{"object":"response.input_tokens","input_tokens":6000}]',
        b'{"object":"response.input_tokens","input_tokens":',
    ],
    ids=[
        "duplicate-input-tokens",
        "duplicate-object",
        "nested-duplicate",
        "boolean",
        "negative",
        "float",
        "numeric-string",
        "null",
        "object-count",
        "missing-count",
        "missing-discriminator",
        "wrong-discriminator",
        "non-object-envelope",
        "malformed-json",
    ],
)
def test_sdk_invalid_raw_count_stops_before_reservation(openai_context, fake_sdk, caplog, body):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    handlers[COUNT] = lambda _: httpx2.Response(
        200, content=body, headers={"content-type": "application/json"}
    )
    workspace = prepare(client)

    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)

    assert result.status_code == 503
    error = result.json()["error"]
    assert error["code"] == "AI_PREFLIGHT_FAILED" and error["retryable"] is True
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
    assert body.decode() not in result.text and body.decode() not in caplog.text
    assert [item.url.path for item in received] == [COUNT]
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.failure_code == "AI_PREFLIGHT_FAILED"
    assert row.counted_input_tokens is None and row.reserved_cost_usd is None
    assert row.usage is None and row.actual_cost_usd is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity"])
@pytest.mark.parametrize("stage", [COUNT, CREATE], ids=["count", "generation"])
def test_sdk_non_json_numeric_literal_is_rejected(openai_context, fake_sdk, stage, literal):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    if stage == COUNT:
        body = (
            b'{"object":"response.input_tokens","input_tokens":6000,"diagnostic":' + literal + b"}"
        )
    else:
        body = (
            json.dumps(provider_response())
            .encode()
            .replace(b'"annotations": []', b'"annotations": [' + literal + b"]")
        )
    handlers[stage] = lambda _: httpx2.Response(
        200, content=body, headers={"content-type": "application/json"}
    )
    workspace = prepare(client)
    result = generate(client, workspace)

    if stage == COUNT:
        assert result.status_code == 503 and result.json()["error"]["code"] == "AI_PREFLIGHT_FAILED"
        assert [item.url.path for item in received] == [COUNT]
    else:
        assert result.status_code == 502 and result.json()["error"]["code"] == "AI_OUTPUT_INVALID"
        assert [item.url.path for item in received] == [COUNT, CREATE]
    (row,) = attempts(connection, workspace)
    assert (row.reserved_cost_usd is None) == (stage == COUNT)
    assert row.status == "failed" and row.normalized_output is None
    assert row.usage is None and row.actual_cost_usd is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "item",
    [
        {"type": "reasoning"},
        {"type": "reasoning", "id": "rs_offline", "summary": [{"type": "summary_text", "text": 1}]},
        {"type": "reasoning", "id": "rs_offline", "summary": [], "status": "in_progress"},
        {"type": "message", "role": "assistant", "status": "completed", "content": []},
        {"type": "function_call", "call_id": "call_offline", "name": "test", "arguments": "{}"},
    ],
    ids=["bare-reasoning", "invalid-summary", "unfinished-reasoning", "missing-message-id", "tool"],
)
def test_sdk_invalid_output_item_does_not_publish_or_store_usage(openai_context, fake_sdk, item):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    response = provider_response()
    response["output"].insert(0, item)
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)
    result = generate(client, workspace)

    assert result.status_code == 502 and result.json()["error"]["code"] == "AI_OUTPUT_INVALID"
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.normalized_output is None
    assert row.usage is None and row.actual_cost_usd is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "reasoning_fields",
    [
        {"summary": []},
        {
            "summary": [{"type": "summary_text", "text": PRIVATE}],
            "content": [{"type": "reasoning_text", "text": PRIVATE}],
            "encrypted_content": PRIVATE,
            "status": "completed",
        },
    ],
    ids=["empty-summary", "full-reasoning-item"],
)
def test_sdk_valid_reasoning_item_allows_findings(
    openai_context, fake_sdk, caplog, reasoning_fields
):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    response = provider_response()
    response["output"].insert(0, {"type": "reasoning", "id": "rs_offline", **reasoning_fields})
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)

    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)

    assert result.status_code == 201, result.text
    (row,) = attempts(connection, workspace)
    assert row.normalized_output == cited_output() and row.actual_cost_usd == Decimal("0.00135")
    assert PRIVATE not in result.text and PRIVATE not in caplog.text


def test_sdk_rejected_model_metadata_is_absent_from_storage_and_reload(
    openai_context, fake_sdk, caplog
):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    response = provider_response(model=REJECTED_MODEL, id=f"resp_{REJECTED_MODEL}")
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)

    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)
        reloaded = read(client, workspace)

    assert result.status_code == 503 and result.json()["error"]["code"] == "AI_CONFIGURATION_ERROR"
    assert result.json()["error"]["retryable"] is False
    assert reloaded.status_code == 200
    assert REJECTED_MODEL not in result.text + reloaded.text + caplog.text
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.configured_model == MODEL
    assert row.returned_model is None and row.provider_response_id is None
    assert row.usage is None and row.actual_cost_usd is None
    history = reloaded.json()["generation_history"][0]
    assert history["configured_model"] == MODEL and history["returned_model"] is None
    assert history["usage"] is None and history["actual_cost_usd"] is None
    assert graph_counts(connection, workspace) == [0] * 5
    assert [request.url.path for request in received] == [COUNT, CREATE]


def test_findings_history_redacts_preexisting_rejected_model(openai_context, fake_sdk, caplog):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    handlers[CREATE] = lambda _: httpx2.Response(200, json=provider_response(model=REJECTED_MODEL))
    workspace = prepare(client)
    assert generate(client, workspace).status_code == 503
    (row,) = attempts(connection, workspace)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db, db.begin():
        stored = db.get(AIGenerationRequest, (row.state_id, row.generation_id))
        stored.returned_model = REJECTED_MODEL
        stored.usage = {"input_tokens": 6000, "output_tokens": 1500}

    with caplog.at_level(logging.DEBUG):
        reloaded = read(client, workspace)

    assert reloaded.status_code == 200
    assert REJECTED_MODEL not in reloaded.text and REJECTED_MODEL not in caplog.text
    history = reloaded.json()["generation_history"][0]
    assert history["failure_code"] == "AI_CONFIGURATION_ERROR" and history["returned_model"] is None
    assert history["usage"] is None and history["actual_cost_usd"] is None


@pytest.mark.parametrize(
    "scenario,status,code",
    [
        ("refusal", 422, "AI_REFUSED"),
        ("incomplete", 502, "AI_OUTPUT_INCOMPLETE"),
        ("failed", 503, "AI_PROVIDER_UNAVAILABLE"),
        ("invalid_json", 502, "AI_OUTPUT_INVALID"),
        ("too_long", 502, "AI_OUTPUT_INVALID"),
        ("null_byte", 502, "AI_OUTPUT_INVALID"),
        ("unreturned", 502, "AI_REFERENCE_INVALID"),
    ],
)
def test_sdk_rejected_output_keeps_usage_without_publishing(
    openai_context, fake_sdk, scenario, status, code
):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    output = cited_output()
    if scenario == "too_long":
        output["findings"][0]["claim"] = "a" * 241
    if scenario == "null_byte":
        output["findings"][0]["claim"] = "Invalid\x00text"
    if scenario == "unreturned":
        output["findings"][0]["citations"][0]["evidence_record_id"] = "SYN-UNRETURNED"
    text = PRIVATE if scenario == "invalid_json" else json.dumps(output)
    parts = [{"type": "output_text", "text": text, "annotations": []}]
    if scenario == "refusal":
        parts.append({"type": "refusal", "refusal": PRIVATE})
    response = provider_response(parts=parts)
    if scenario in {"incomplete", "failed"}:
        response["status"] = scenario
    if scenario == "incomplete":
        response["incomplete_details"] = {"reason": "max_output_tokens"}
    if scenario == "failed":
        response["error"] = {"code": "server_error", "message": PRIVATE}
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == status and result.json()["error"]["code"] == code
    assert PRIVATE not in result.text
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.normalized_output is None
    assert row.provider_response_id == RESPONSE_ID and row.usage["input_tokens"] == 6000
    assert row.returned_model == response["model"]
    assert row.actual_cost_usd == Decimal("0.00135")
    assert graph_counts(connection, workspace) == [0] * 5
    assert [item.url.path for item in received] == [COUNT, CREATE]


@pytest.mark.parametrize(
    "stage,failure,status,code",
    [
        (COUNT, httpx2.ConnectError, "failed", "AI_PREFLIGHT_FAILED"),
        (CREATE, httpx2.ConnectError, "failed", "AI_PROVIDER_UNAVAILABLE"),
        (CREATE, httpx2.ReadTimeout, "interrupted", "AI_DEADLINE_EXCEEDED"),
    ],
)
def test_sdk_transport_exception_maps_to_safe_outcome(
    openai_context, fake_sdk, caplog, stage, failure, status, code
):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk

    def fail(request):
        raise failure(PRIVATE, request=request)

    handlers[stage] = fail
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == 503 and result.json()["error"]["code"] == code
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
    assert [item.url.path for item in received] == ([COUNT] if stage == COUNT else [COUNT, CREATE])
    (row,) = attempts(connection, workspace)
    assert row.status == status and row.usage is None and row.actual_cost_usd is None


@pytest.mark.parametrize("stage", [COUNT, CREATE])
def test_sdk_timeout_cancels_transport_and_keeps_unknown_cost(openai_context, fake_sdk, stage):
    client, connection, app, _, _ = openai_context
    received, handlers = fake_sdk
    cancelled = Event()

    async def stall(_):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    handlers[stage] = stall
    limit = (
        "ai_findings_count_timeout_seconds"
        if stage == COUNT
        else "ai_findings_model_timeout_seconds"
    )
    app.state.settings = app.state.settings.model_copy(update={limit: 0.1})
    workspace = prepare(client)
    result = generate(client, workspace)
    assert result.status_code == 503 and result.json()["error"]["code"] == "AI_DEADLINE_EXCEEDED"
    assert cancelled.is_set()
    assert [item.url.path for item in received] == ([COUNT] if stage == COUNT else [COUNT, CREATE])
    (row,) = attempts(connection, workspace)
    assert row.status == "interrupted" and row.usage is None and row.actual_cost_usd is None
    assert (row.reserved_cost_usd is not None) == (stage == CREATE)
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "malformed",
    [
        {"object": "response.input_tokens"},
        {"error": {"code": "server_error", "message": PRIVATE}},
        {"incomplete_details": {"reason": "max_output_tokens"}},
    ],
    ids=["object", "response-error", "completed-with-incomplete-details"],
)
def test_sdk_malformed_envelope_cannot_publish(openai_context, fake_sdk, malformed):
    client, connection, _, _, _ = openai_context
    received, handlers = fake_sdk
    handlers[CREATE] = lambda _: httpx2.Response(200, json=provider_response(**malformed))
    workspace = prepare(client)

    result = generate(client, workspace)
    assert result.status_code == 502 and result.json()["error"]["code"] == "AI_OUTPUT_INVALID"
    assert PRIVATE not in result.text
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.normalized_output is None
    assert graph_counts(connection, workspace) == [0] * 5
    assert [request.url.path for request in received] == [COUNT, CREATE]


@pytest.mark.parametrize(
    "original,duplicate",
    [
        (b'"object": "response"', b'"object": "response.input_tokens", "object": "response"'),
        (
            b'"error": null',
            b'"error": {"message": "private-provider-test-marker"}, "error": null',
        ),
        (
            b'"incomplete_details": null',
            b'"incomplete_details": {"reason": "max_output_tokens"}, "incomplete_details": null',
        ),
        (b'"type": "output_text"', b'"type": "refusal", "type": "output_text"'),
    ],
    ids=["object", "error", "incomplete-details", "nested-output-part"],
)
def test_sdk_duplicate_response_fields_block_publication(
    openai_context, fake_sdk, caplog, original, duplicate
):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    body = json.dumps(provider_response(error=None, incomplete_details=None)).encode()
    assert body.count(original) == 1
    handlers[CREATE] = lambda _: httpx2.Response(
        200, content=body.replace(original, duplicate), headers={"content-type": "application/json"}
    )
    workspace = prepare(client)

    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)

    assert result.status_code == 502 and result.json()["error"]["code"] == "AI_OUTPUT_INVALID"
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
    (row,) = attempts(connection, workspace)
    assert row.status == "failed" and row.normalized_output is None
    assert row.usage is None and row.actual_cost_usd is None
    assert graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize(
    "original,duplicate",
    [
        (b'"usage": {', b'"usage": null, "usage": {'),
        (b'"input_tokens": 6000', b'"input_tokens": true, "input_tokens": 6000'),
        (b'"cached_tokens": 0', b'"cached_tokens": -1, "cached_tokens": 0'),
        (
            b'"cache_write_tokens": 0',
            b'"cache_write_tokens": 0, "cache_write_tokens_details": '
            b'{"ttl_30m_tokens": false, "ttl_30m_tokens": 0, "ttl_12h_tokens": 0}',
        ),
    ],
    ids=["usage-field", "input-tokens", "nested-cache-read", "nested-cache-write-lifetime"],
)
def test_sdk_duplicate_usage_fields_leave_accounting_unknown(
    openai_context, fake_sdk, caplog, original, duplicate
):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    body = json.dumps(provider_response()).encode()
    assert body.count(original) == 1
    handlers[CREATE] = lambda _: httpx2.Response(
        200, content=body.replace(original, duplicate), headers={"content-type": "application/json"}
    )
    workspace = prepare(client)

    with caplog.at_level(logging.DEBUG):
        result = generate(client, workspace)

    assert result.status_code == 201, result.text
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
    (row,) = attempts(connection, workspace)
    assert row.status == "completed" and row.usage is None and row.actual_cost_usd is None
    history = read(client, workspace).json()["generation_history"][0]
    assert history["usage"] is None and history["actual_cost_usd"] is None
    assert graph_counts(connection, workspace) == [1, 1, 1, 1, 0]


@pytest.mark.parametrize("elapsed", [15, 21], ids=["publication-reserve", "expired"])
def test_sdk_utc_deadline_after_reservation_prevents_generation(
    openai_context, fake_sdk, monkeypatch, elapsed
):
    client, connection, _, clock, _ = openai_context
    received, _ = fake_sdk
    reserve = findings.reserve
    monkeypatch.setattr(findings, "monotonic", lambda: 100.0)

    def advance_after_reservation(*args):
        reserve(*args)
        clock.now += timedelta(seconds=elapsed)

    monkeypatch.setattr(findings, "reserve", advance_after_reservation)
    workspace = prepare(client)
    result = generate(client, workspace)

    assert [request.url.path for request in received] == [COUNT]
    assert result.status_code == 503 and result.json()["error"]["code"] == "AI_DEADLINE_EXCEEDED"
    (row,) = attempts(connection, workspace)
    assert row.status == "interrupted" and row.retryable
    assert row.reserved_cost_usd == Decimal("0.0021") and row.usage is None
    assert row.actual_cost_usd is None and graph_counts(connection, workspace) == [0] * 5


@pytest.mark.parametrize("limited_clock", ["utc", "monotonic"])
def test_sdk_generation_timeout_uses_earlier_deadline(
    openai_context, fake_sdk, monkeypatch, limited_clock
):
    client, _, _, clock, _ = openai_context
    received, _ = fake_sdk
    reserve = findings.reserve
    monotonic_time = 100.0
    monkeypatch.setattr(findings, "monotonic", lambda: monotonic_time)

    def advance_after_reservation(*args):
        nonlocal monotonic_time
        reserve(*args)
        if limited_clock == "utc":
            clock.now += timedelta(seconds=12)
        else:
            monotonic_time += 12

    monkeypatch.setattr(findings, "reserve", advance_after_reservation)
    assert generate(client, prepare(client)).status_code == 201
    assert [request.url.path for request in received] == [COUNT, CREATE]
    assert received[1].extensions["timeout"]["read"] == 2.0


@pytest.mark.parametrize(
    "usage_changes",
    [
        {"input_tokens": True},
        {"output_tokens": -1},
        {"input_tokens": "6000"},
        {"output_tokens": 1500.0},
        {"total_tokens": None},
        {"total_tokens": 7501},
        {"input_tokens_details": []},
        {"input_tokens_details": {"cached_tokens": "0", "cache_write_tokens": 0}},
        {"input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 3000}},
        {"input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 6001}},
        {
            "input_tokens_details": {
                "cached_tokens": 0,
                "cache_write_tokens": 10,
                "cache_write_tokens_details": {"ttl_30m_tokens": 5, "ttl_12h_tokens": 4},
            }
        },
        {"output_tokens_details": {"reasoning_tokens": 1501}},
    ],
    ids=[
        "boolean",
        "negative",
        "integer-string",
        "float",
        "null-total",
        "wrong-total",
        "non-object-breakdown",
        "coercible-cache-count",
        "cache-sum-exceeds-input",
        "writes-exceed-input",
        "wrong-cache-lifetime-sum",
        "reasoning-exceeds-output",
    ],
)
def test_sdk_malformed_raw_usage_is_not_persisted(openai_context, fake_sdk, usage_changes):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    response = provider_response()
    response["usage"].update(usage_changes)
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)

    result = generate(client, workspace)
    assert result.status_code == 201, result.text
    (row,) = attempts(connection, workspace)
    assert row.usage is None and row.actual_cost_usd is None
    history = read(client, workspace).json()["generation_history"][0]
    assert history["usage"] is None and history["actual_cost_usd"] is None
    assert graph_counts(connection, workspace) == [1, 1, 1, 1, 0]


@pytest.mark.parametrize("input_details", [{"cached_tokens": 0}, {"cache_write_tokens": 0}])
def test_sdk_missing_cache_evidence_leaves_cost_unknown(openai_context, fake_sdk, input_details):
    client, connection, _, _, _ = openai_context
    _, handlers = fake_sdk
    response = provider_response()
    response["usage"]["input_tokens_details"] = input_details
    handlers[CREATE] = lambda _: httpx2.Response(200, json=response)
    workspace = prepare(client)

    assert generate(client, workspace).status_code == 201
    (row,) = attempts(connection, workspace)
    assert row.usage["total_tokens"] == 7500 and row.actual_cost_usd is None
    assert ("cached_input_tokens" in row.usage) == ("cached_tokens" in input_details)
    assert ("cache_write_tokens" in row.usage) == ("cache_write_tokens" in input_details)


def test_sdk_discards_provider_cookies_across_endpoints_and_visitors(openai_context, fake_sdk):
    client, _, app, _, first_visitor = openai_context
    received, handlers = fake_sdk
    for path in (COUNT, CREATE):
        handler = handlers[path]

        def issue_cookie(request, handler=handler):
            response = handler(request)
            response.headers["set-cookie"] = "provider_session=offline; Path=/; Secure"
            return response

        handlers[path] = issue_cookie

    shared_provider = app.state.findings_provider
    first = generate(client, prepare(client))
    assert first.status_code == 201, first.text
    client.cookies.clear()
    second_visitor = bootstrap(client)
    assert first_visitor["visitor_context_id"] != second_visitor["visitor_context_id"]
    second = generate(client, prepare(client))
    assert second.status_code == 201, second.text
    assert app.state.findings_provider is shared_provider
    assert [request.url.path for request in received] == [COUNT, CREATE, COUNT, CREATE]
    assert all("cookie" not in request.headers for request in received)


def test_environment_key_is_only_loaded_for_explicit_openai_selection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/unused")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("AI_FINDINGS_ENABLED", "false")
    monkeypatch.setenv("AI_FINDINGS_PROVIDER", "openai")
    assert Settings.from_env().openai_api_key is None
    monkeypatch.setenv("AI_FINDINGS_ENABLED", "true")
    monkeypatch.setenv("AI_FINDINGS_PROVIDER", "mock")
    assert Settings.from_env().openai_api_key is None
    monkeypatch.setenv("AI_FINDINGS_PROVIDER", "openai")
    settings = Settings.from_env()
    assert settings.openai_api_key is not None
    assert FAKE_KEY not in repr(settings)
    assert "openai_api_key" not in settings.model_dump()


def test_sdk_ambient_headers_prevent_provider_startup(monkeypatch):
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Cookie: offline-test-placeholder")
    provider = openai_findings_provider.build_openai_provider(SecretStr(FAKE_KEY))
    assert provider is None
