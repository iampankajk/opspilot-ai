"""Offline wire checks and deployment-wide admission on real PostgreSQL transactions."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx2
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import DateTime, event, func, literal, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from test_evidence import retrieve
from test_findings import attempts, generate, graph_counts, prepare, read
from test_investigations import Clock, bootstrap
from test_openai_findings import cited_output

from app import evidence, findings
from app.config import GEMINI_FINDINGS_MODEL, Settings
from app.database import build_engine
from app.findings_provider import MockFindingsProvider, ProviderFailure
from app.findings_schemas import FindingGenerationCreate, FindingGenerationOutput
from app.gemini_findings_provider import (
    API_ORIGIN,
    MAX_ERROR_BODY_BYTES,
    build_gemini_provider,
    gemini_response_options,
    guard_request,
    validate_response_encoding,
)
from app.main import create_app
from app.models import AIGenerationRequest, WorkingDraft
from app.visitor_sessions import get_clock

MODEL = GEMINI_FINDINGS_MODEL
COUNT = f"/v1/models/{MODEL}:countTokens"
GENERATE = f"/v1/models/{MODEL}:generateContent"
FAKE_KEY = "gemini-offline-key-placeholder"


def build_synthetic_aq_key(infix: str = "") -> str:
    """Assemble a 53-char synthetic AQ. test key at runtime without a contiguous literal."""
    prefix = ".".join(("AQ", "offline"))
    label = "_".join(("synthetic", "test", "key"))
    suffix = "0123456789abcdef" * 3
    key = f"{prefix}-{infix}{label}_{suffix}"[:53]
    assert len(key) == 53 and key.startswith("AQ.")
    return key


SYNTHETIC_AQ_KEY = build_synthetic_aq_key()
RESPONSE_ID = "offline_response_ID-2"
PRIVATE = "private-gemini-test-marker"
EMPTY = {"schema_version": "task5.v1", "findings": [], "no_findings_reason": "no_assessable_claims"}


def gemini_body(*, output=None, finish="STOP", **overrides):
    text = json.dumps(cited_output() if output is None else output)
    return {
        "candidates": [
            {
                "index": 0,
                "finishReason": finish,
                "content": {
                    "role": "model",
                    "parts": [{"text": text}],
                },
            }
        ],
        "modelVersion": MODEL,
        "responseId": RESPONSE_ID,
        "usageMetadata": {
            "promptTokenCount": 6001,
            "candidatesTokenCount": 400,
            "thoughtsTokenCount": 7,
            "cachedContentTokenCount": 4,
            "totalTokenCount": 6408,
            "serviceTier": PRIVATE,
        },
    } | overrides


@pytest.fixture(scope="module")
def migration_ddl():
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    return output.getvalue().replace("BEGIN;", "").replace("COMMIT;", "")


@pytest.fixture
def deployment(database, migration_ddl, monkeypatch):
    engine, settings = database
    schema = "gemini_test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql(migration_ddl)

    def worker_engine(worker_settings):
        worker = build_engine(worker_settings)
        worker.update_execution_options(schema_translate_map={None: schema})
        return worker

    monkeypatch.setattr("app.main.build_engine", worker_engine)
    config = settings.model_copy(
        update={
            "ai_findings_enabled": True,
            "ai_findings_provider": "gemini",
            "gemini_api_key": SecretStr(FAKE_KEY),
            # The OpenAI-only setting cannot prevent Gemini from running.
            "ai_findings_model": "unreviewed-openai-model",
        }
    )
    try:
        yield engine.execution_options(schema_translate_map={None: schema}), config
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def install_wire(monkeypatch, *, expected_key: str = FAKE_KEY):
    received = []
    handlers = {
        COUNT: lambda _: httpx2.Response(200, json={"totalTokens": 6000}),
        GENERATE: lambda _: httpx2.Response(200, json=gemini_body()),
    }

    async def dispatch(_transport, request):
        assert request.method == "POST"
        assert request.url.scheme == "https"
        assert request.url.host == "generativelanguage.googleapis.com"
        assert not request.url.query
        assert request.headers["x-goog-api-key"] == expected_key
        assert (
            not {"cookie", "cookie2", "authorization", "x-goog-user-project"}
            & request.headers.keys()
        )
        assert all(
            marker not in request.content for marker in (expected_key.encode(), b"postgresql+")
        )
        received.append(request)
        response = handlers[request.url.path](request)
        if asyncio.iscoroutine(response):
            return await response
        return response

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", dispatch)
    return received, handlers


@pytest.fixture
def wire(monkeypatch):
    return install_wire(monkeypatch)


def worker(config, clock=None):
    app = create_app(config)
    if clock is not None:
        app.dependency_overrides[get_clock] = lambda: clock
    return TestClient(app, base_url="https://localhost:3000")


@pytest.fixture
def gemini(deployment, wire):
    engine, config = deployment
    with worker(config) as client:
        bootstrap(client)
        yield client, engine
    assert client.app.state.findings_provider.transport.is_closed


def check_error(response, status, code, retryable=True):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code and error["retryable"] is retryable
    return error["details"]


def test_settings_load_only_the_enabled_provider_key(monkeypatch):
    monkeypatch.setattr("app.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test@localhost/opspilot_test")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-google-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-openai-key")
    monkeypatch.delenv("AI_FINDINGS_PROVIDER", raising=False)
    monkeypatch.delenv("AI_FINDINGS_ENABLED", raising=False)
    monkeypatch.delenv("AI_FINDINGS_GEMINI_MODEL", raising=False)
    config = Settings.from_env()
    assert config.ai_findings_provider == "mock" and not config.ai_findings_enabled
    assert config.gemini_api_key is None and config.openai_api_key is None
    monkeypatch.setenv("AI_FINDINGS_PROVIDER", "gemini")
    assert Settings.from_env().gemini_api_key is None
    monkeypatch.setenv("AI_FINDINGS_ENABLED", "true")
    config = Settings.from_env()
    assert config.gemini_api_key == SecretStr(FAKE_KEY) and config.openai_api_key is None
    assert config.ai_findings_gemini_model == MODEL
    assert "gemini_api_key" not in config.model_dump() and FAKE_KEY not in repr(config)
    monkeypatch.delenv("GEMINI_API_KEY")
    assert Settings.from_env().gemini_api_key is None


@pytest.mark.parametrize(
    "update,code",
    [
        ({"ai_findings_enabled": False}, "AI_NOT_CONFIGURED"),
        ({"gemini_api_key": None}, "AI_CONFIGURATION_ERROR"),
        ({"gemini_api_key": SecretStr("invalid\r\nheader")}, "AI_CONFIGURATION_ERROR"),
        ({"gemini_api_key": SecretStr("AQ.invalid key")}, "AI_CONFIGURATION_ERROR"),
        ({"gemini_api_key": SecretStr("A" * 257)}, "AI_CONFIGURATION_ERROR"),
        ({"ai_findings_gemini_model": "other-model"}, "AI_CONFIGURATION_ERROR"),
    ],
)
def test_incompatible_config_never_builds_or_calls_an_adapter(deployment, wire, update, code):
    engine, config = deployment
    with worker(config.model_copy(update=update)) as client:
        bootstrap(client)
        workspace = prepare(client)
        assert client.app.state.findings_provider is None
        check_error(generate(client, workspace), 503, code, False)
        assert attempts(engine, workspace) == [] and wire[0] == []


@pytest.mark.parametrize(
    "candidate",
    [
        SYNTHETIC_AQ_KEY,
        "!",
        "".join(chr(code) for code in range(0x21, 0x7F)),
        "A" * 256,
    ],
    ids=["synthetic-aq-53", "min-len-1", "all-printable-ascii", "max-len-256"],
)
def test_build_gemini_provider_accepts_printable_ascii_keys(candidate):
    assert len(SYNTHETIC_AQ_KEY) == 53 and SYNTHETIC_AQ_KEY.startswith("AQ.")

    async def check():
        provider = await build_gemini_provider(SecretStr(candidate))
        assert provider is not None
        try:
            assert provider._key.get_secret_value() == candidate
            assert not provider.transport.is_closed
        finally:
            await provider.close()
        assert provider.transport.is_closed

    asyncio.run(check())


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        "",
        " ",
        " AQ.key",
        "AQ.key ",
        "AQ. key",
        "AQ.\tkey",
        "AQ.\nkey",
        "AQ.key\n",
        "AQ.\rkey",
        "invalid\r\nheader",
        "AQ.\x00key",
        "AQ.\x1fkey",
        "AQ.\x7fkey",
        "AQ.kéy",
        "AQ.\u00a0key",
        "AQ.\u200bkey",
        "A" * 257,
    ],
    ids=[
        "none",
        "empty",
        "space-only",
        "leading-space",
        "trailing-space",
        "internal-space",
        "tab",
        "lf",
        "trailing-lf",
        "cr",
        "crlf",
        "nul",
        "unit-separator",
        "del",
        "non-ascii",
        "nbsp",
        "zero-width-space",
        "over-256",
    ],
)
def test_build_gemini_provider_rejects_unsafe_or_oversized_keys(candidate):
    secret = None if candidate is None else SecretStr(candidate)
    assert asyncio.run(build_gemini_provider(secret)) is None


def test_synthetic_aq_key_runs_findings_generation_without_leaking(
    deployment, monkeypatch, capsys, caplog
):
    assert len(SYNTHETIC_AQ_KEY) == 53 and SYNTHETIC_AQ_KEY.startswith("AQ.")
    monkeypatch.setattr("app.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test@localhost/opspilot_test")
    monkeypatch.setenv("AI_FINDINGS_ENABLED", "true")
    monkeypatch.setenv("AI_FINDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", SYNTHETIC_AQ_KEY)
    loaded = Settings.from_env()
    assert loaded.gemini_api_key == SecretStr(SYNTHETIC_AQ_KEY)
    assert "gemini_api_key" not in loaded.model_dump() and SYNTHETIC_AQ_KEY not in repr(loaded)

    engine, config = deployment
    received, _ = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        assert client.app.state.findings_provider is not None
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        assert response.status_code == 201, response.text
        assert response.json()["findings"]
        reloaded = read(client, workspace)
        assert reloaded.status_code == 200, reloaded.text
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "completed" and row.returned_model == MODEL
    for text_blob in (
        response.text,
        reloaded.text,
        caplog.text,
        capture.out,
        capture.err,
        str(vars(row)),
    ):
        assert SYNTHETIC_AQ_KEY not in text_blob


@pytest.mark.parametrize(
    "scenario,status,code",
    [
        ("upstream-error", 503, "AI_PROVIDER_UNAVAILABLE"),
        ("leaked-output", 502, "AI_OUTPUT_INVALID"),
    ],
)
def test_synthetic_aq_key_error_paths_never_leak_key(
    deployment, monkeypatch, capsys, caplog, scenario, status, code
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    if scenario == "upstream-error":
        handlers[GENERATE] = lambda _: httpx2.Response(
            503,
            json={"error": {"message": f"{PRIVATE} {SYNTHETIC_AQ_KEY}"}},
        )
    else:
        output = cited_output()
        output["findings"][0]["claim"] = SYNTHETIC_AQ_KEY
        handlers[GENERATE] = lambda _: httpx2.Response(
            200,
            json=gemini_body(output=output, responseId=SYNTHETIC_AQ_KEY),
        )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, status, code, True)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == code
    assert row.normalized_output is None and row.provider_response_id is None
    for text_blob in (
        response.text,
        caplog.text,
        capture.out,
        capture.err,
        str(vars(row)),
    ):
        assert SYNTHETIC_AQ_KEY not in text_blob
    assert PRIVATE not in response.text and PRIVATE not in caplog.text


QUOTED_KEY = build_synthetic_aq_key('"')
BACKSLASH_KEY = build_synthetic_aq_key("\\")
QUOTED_BACKSLASH_KEY = build_synthetic_aq_key('"\\')


def nested_output_with_secret(location: str, secret: str) -> dict:
    output = cited_output()
    finding = output["findings"][0]
    finding["limitations"] = [
        {
            "text": "Additional bank evidence is missing.",
            "kind": "evidence_statement",
            "citation_indexes": [0],
            "result_source_keys": [],
        }
    ]
    finding["next_questions"] = ["Was a separate bank debit posted?"]
    match location:
        case "claim":
            finding["claim"] = f"Observed marker {secret}"
        case "citation_explanation":
            finding["citations"][0]["explanation"] = f"Explanation {secret}"
        case "citation_pointer":
            finding["citations"][0]["pointer"] = f"/payload/{secret}"
        case "rationale_text":
            finding["rationale"][0]["text"] = f"Rationale {secret}"
        case "limitation_text":
            finding["limitations"][0]["text"] = f"Limitation {secret}"
        case "next_question":
            finding["next_questions"][0] = f"Follow up on {secret}?"
        case _:
            raise AssertionError(f"Unsupported test location: {location}")
    return output


@pytest.mark.parametrize(
    "api_key,location",
    [
        (QUOTED_KEY, "claim"),
        (BACKSLASH_KEY, "claim"),
        (QUOTED_BACKSLASH_KEY, "claim"),
        (QUOTED_BACKSLASH_KEY, "citation_explanation"),
        (QUOTED_BACKSLASH_KEY, "citation_pointer"),
        (QUOTED_BACKSLASH_KEY, "rationale_text"),
        (QUOTED_BACKSLASH_KEY, "limitation_text"),
        (QUOTED_BACKSLASH_KEY, "next_question"),
        (SYNTHETIC_AQ_KEY, "claim"),
        (SYNTHETIC_AQ_KEY, "rationale_text"),
    ],
    ids=[
        "quote-in-claim",
        "backslash-in-claim",
        "quote-and-backslash-in-claim",
        "nested-citation-explanation",
        "nested-citation-pointer",
        "nested-rationale-text",
        "nested-limitation-text",
        "nested-next-question",
        "aq-key-in-claim",
        "aq-key-in-rationale",
    ],
)
def test_reflected_gemini_credentials_including_json_escapes_are_rejected(
    deployment, monkeypatch, capsys, caplog, api_key, location
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=api_key)
    handlers[GENERATE] = lambda _: httpx2.Response(
        200,
        json=gemini_body(output=nested_output_with_secret(location, api_key)),
    )
    key_config = config.model_copy(update={"gemini_api_key": SecretStr(api_key)})
    with worker(key_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 502, "AI_OUTPUT_INVALID", True)
        reloaded = read(client, workspace)
        assert reloaded.status_code == 200, reloaded.text
        reloaded_body = reloaded.json()
        assert reloaded_body["findings"] == []
        assert reloaded_body["generation_status"] == "failed"
        assert reloaded_body["generation_history"][0]["failure_code"] == "AI_OUTPUT_INVALID"
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert graph_counts(engine, workspace) == [0] * 5
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_OUTPUT_INVALID"
    assert row.normalized_output is None and row.provider_response_id == RESPONSE_ID
    escaped_key = json.dumps(api_key)[1:-1]
    for text_blob in (
        response.text,
        reloaded.text,
        caplog.text,
        capture.out,
        capture.err,
        str(vars(row)),
    ):
        assert api_key not in text_blob
        assert escaped_key not in text_blob


@pytest.mark.parametrize(
    "api_key",
    [SYNTHETIC_AQ_KEY, QUOTED_BACKSLASH_KEY],
    ids=["synthetic-aq-53", "quote-and-backslash-key"],
)
def test_valid_findings_without_reflected_credentials_succeed_for_escaped_keys(
    deployment, monkeypatch, capsys, caplog, api_key
):
    engine, config = deployment
    received, _ = install_wire(monkeypatch, expected_key=api_key)
    key_config = config.model_copy(update={"gemini_api_key": SecretStr(api_key)})
    with worker(key_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        assert response.status_code == 201, response.text
        assert response.json()["findings"]
        reloaded = read(client, workspace)
        assert reloaded.status_code == 200, reloaded.text
        assert reloaded.json()["findings"] == response.json()["findings"]
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert graph_counts(engine, workspace) == [1, 1, 1, 1, 0]
    (row,) = attempts(engine, workspace)
    assert row.status == "completed" and row.returned_model == MODEL
    escaped_key = json.dumps(api_key)[1:-1]
    for text_blob in (
        response.text,
        reloaded.text,
        caplog.text,
        capture.out,
        capture.err,
        str(vars(row)),
    ):
        assert api_key not in text_blob
        assert escaped_key not in text_blob


@pytest.mark.parametrize(
    "mode,seed_replay", [("record", False), ("replay", True), ("auto", False), ("auto", True)]
)
def test_ambient_debug_modes_cannot_record_or_replay(
    wire, monkeypatch, tmp_path, capsys, caplog, mode, seed_replay
):
    received, handlers = wire
    replay_id = "opspilot/offline_gemini/mldev"
    replay_path = tmp_path / f"{replay_id}.json"
    evidence_marker = "synthetic debug-regression evidence"
    bundle = {
        "instructions": "Assess the synthetic offline bundle.",
        "context": {},
        "evidence": {"example": evidence_marker},
        "response_options": gemini_response_options(3000),
    }
    body = gemini_body()
    body["candidates"][0]["content"]["parts"].insert(0, {"thought": True, "text": PRIVATE})
    handlers[GENERATE] = lambda _: httpx2.Response(200, json=body)

    async def invoke():
        provider = await build_gemini_provider(SecretStr(FAKE_KEY))
        try:
            count = await provider.count_input(bundle, timeout=3)
            result = await provider.generate(bundle, timeout=10)
        finally:
            await provider.close()
        assert provider.transport.is_closed
        assert count.input_tokens == 6000
        return result

    replay_bytes = None
    if seed_replay:
        with monkeypatch.context() as baseline:
            baseline.setenv("GOOGLE_GENAI_CLIENT_MODE", "api")
            asyncio.run(invoke())
        request = received.pop()
        received.clear()
        replay_body = gemini_body(output=EMPTY)
        headers = dict(httpx2.Response(200, json=replay_body).headers)
        recorded = {
            "request": {
                "method": "POST",
                "url": str(request.url),
                "headers": {},
                "body_segments": [json.loads(request.content)],
            },
            "response": {
                "headers": headers,
                "body_segments": [replay_body],
                "sdk_response_segments": [
                    {"sdk_http_response": {"headers": headers, "body": json.dumps(replay_body)}}
                ],
            },
        }
        replay_bytes = json.dumps({"replay_id": replay_id, "interactions": [recorded]}).encode()
        replay_path.parent.mkdir(parents=True)
        replay_path.write_bytes(replay_bytes)

    monkeypatch.setenv("GOOGLE_GENAI_CLIENT_MODE", mode)
    monkeypatch.setenv("GOOGLE_GENAI_REPLAYS_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("GOOGLE_GENAI_REPLAY_ID", replay_id)
    with caplog.at_level(logging.DEBUG):
        result = asyncio.run(invoke())
    capture = capsys.readouterr()
    for marker in (FAKE_KEY, PRIVATE, evidence_marker):
        assert marker not in capture.out + capture.err + caplog.text
    assert capture.out == capture.err == ""
    assert [item.url.path for item in received] == [COUNT, GENERATE]
    assert json.loads(result.output_json) == cited_output()
    assert list(tmp_path.rglob("*.json")) == ([replay_path] if seed_replay else [])
    if seed_replay:
        assert replay_path.read_bytes() == replay_bytes


def test_full_request_parity_usage_and_private_metadata(deployment, wire, monkeypatch, caplog):
    engine, config = deployment
    received, handlers = wire
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", "https://unexpected.example.invalid")
    monkeypatch.setenv("GOOGLE_GENAI_API_VERSION", "v1beta")
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")
    monkeypatch.setenv("GOOGLE_GENAI_HTTP_CLIENT", "httpx")
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-google-test-key")
    monkeypatch.setenv("HTTPS_PROXY", "https://unexpected.example.invalid:8989")
    with worker(config) as client:
        bootstrap(client)
        workspace = prepare(client)
        provider = client.app.state.findings_provider
        visitor_token = next(iter(client.cookies.jar)).value

        def check_committed_start(_):
            (row,) = attempts(engine, workspace)
            assert row.status == "pending" and row.counted_input_tokens is None
            with engine.begin() as connection:
                assert connection.scalar(
                    select(func.pg_try_advisory_xact_lock(*findings.GEMINI_ADMISSION_LOCK))
                )
            return httpx2.Response(
                200, json={"totalTokens": 6000}, headers={"Set-Cookie": f"vendor={PRIVATE}; Secure"}
            )

        def check_committed_reservation(request):
            (row,) = attempts(engine, workspace)
            assert row.status == "pending" and row.counted_input_tokens == 6000
            assert row.reserved_cost_usd == 0
            assert visitor_token not in request.content.decode()
            body = gemini_body() | {"modelStatus": {"message": PRIVATE}}
            parts = body["candidates"][0]["content"]["parts"]
            text = parts[0]["text"]
            parts[:] = [
                {"thought": True, "text": PRIVATE, "thoughtSignature": PRIVATE},
                {"thoughtSignature": PRIVATE},
                {"thought": True, "thoughtSignature": PRIVATE},
                {"text": text[:17], "thoughtSignature": PRIVATE},
                {"text": text[17:]},
            ]
            return httpx2.Response(200, json=body, headers={"Set-Cookie": f"vendor={PRIVATE}"})

        generate_content = provider.client.aio.models.generate_content

        async def check_sdk_config(*, config, **kwargs):
            assert config.automatic_continuation is False
            assert config.automatic_function_calling.disable is True
            assert config.http_options.retry_options.attempts == 1
            assert 9000 <= config.http_options.timeout <= 10000
            return await generate_content(config=config, **kwargs)

        monkeypatch.setattr(provider.client.aio.models, "generate_content", check_sdk_config)
        handlers[COUNT] = check_committed_start
        handlers[GENERATE] = check_committed_reservation
        assert received == []
        with caplog.at_level(logging.DEBUG):
            result = generate(client, workspace)
        assert result.status_code == 201, result.text
        assert not provider.transport.cookies
        assert all(visitor_token not in item.content.decode() for item in received)
    assert provider.transport.is_closed

    assert [item.url.path for item in received] == [COUNT, GENERATE]
    (row,) = attempts(engine, workspace)
    count, generation = (json.loads(item.content) for item in received)
    assert count == {"generateContentRequest": generation | {"model": f"models/{MODEL}"}}
    assert generation["systemInstruction"] == {"parts": [{"text": findings.INSTRUCTIONS}]}
    (message,) = generation["contents"]
    assert message["role"] == "user"
    assert json.loads(message["parts"][0]["text"].split("\n", 1)[1]) == {
        key: row.input_bundle[key] for key in ("context", "evidence")
    }
    assert set(generation) == {"systemInstruction", "contents", "generationConfig"}
    generation_config = generation["generationConfig"]
    schema = generation_config["responseJsonSchema"]
    assert generation_config == {
        "candidateCount": 1,
        "maxOutputTokens": 3000,
        "responseMimeType": "application/json",
        "responseJsonSchema": schema,
        "thinkingConfig": {"thinkingLevel": "MINIMAL"},
    }
    assert generation_config == row.input_bundle["response_options"]["generationConfig"]
    for object_schema in [schema, *schema["$defs"].values()]:
        assert object_schema["type"] == "object"
        assert object_schema["additionalProperties"] is False
        assert set(object_schema["required"]) == set(object_schema["properties"])
    assert schema["properties"]["schema_version"]["enum"] == ["task5.v1"]
    assert schema["properties"]["findings"]["items"] == {"$ref": "#/$defs/FindingDraft"}
    assert {"type": "null"} in schema["properties"]["no_findings_reason"]["anyOf"]
    for keyword in (
        "minLength",
        "maxLength",
        "pattern",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "title",
    ):
        assert f'"{keyword}":' not in json.dumps(schema)
    assert (
        FindingGenerationOutput.model_json_schema()["$defs"]["FindingDraft"]["properties"]["claim"][
            "maxLength"
        ]
        == 240
    )
    for item, timeout in zip(received, (3.0, 10.0), strict=True):
        assert 0 < item.extensions["timeout"]["read"] <= timeout
        assert item.extensions["timeout"]["read"] >= timeout - 1
    assert row.provider == "gemini" and row.configured_model == row.returned_model == MODEL
    assert row.provider_response_id == RESPONSE_ID
    assert row.budget["token_count_kind"] == "gemini_count_tokens"
    assert row.budget["cost_basis"] == "gemini_developer_api_free_estimate"
    assert row.budget["price_verified_at"] == "2026-11-25"
    assert row.actual_cost_usd is None and row.reserved_cost_usd == 0
    assert row.usage == {
        "input_tokens": 6001,
        "output_tokens": 407,
        "total_tokens": 6408,
        "cached_input_tokens": 4,
        "reasoning_tokens": 7,
    }
    assert row.input_digest == findings.bundle_digest(row.input_bundle)
    assert row.normalized_output == cited_output()
    assert graph_counts(engine, workspace) == [1, 1, 1, 1, 0]
    for marker in (FAKE_KEY, PRIVATE, RESPONSE_ID, findings.INSTRUCTIONS, visitor_token):
        assert marker not in caplog.text
    for marker in (FAKE_KEY, PRIVATE, RESPONSE_ID, visitor_token):
        assert marker not in result.text
    assert PRIVATE not in str(vars(row)) and FAKE_KEY not in str(vars(row))
    assert result.json()["findings"][0]["review_state"] == "awaiting_review"

    with worker(config.model_copy(update={"ai_findings_enabled": False})) as restarted:
        restarted.cookies.update(client.cookies)
        alert = read(restarted, workspace)
        assert alert.status_code == 200, alert.text
        assert {key: alert.json()[key] for key in ("findings", "generation_history")} == {
            key: result.json()[key] for key in ("findings", "generation_history")
        }
    assert len(received) == 2


@pytest.mark.parametrize("count", [None, True, "20", 2.0, -1, 0, 2147483648, 12001])
def test_count_requires_bounded_positive_integer(gemini, wire, count):
    client, engine = gemini
    received, handlers = wire
    handlers[COUNT] = lambda _: httpx2.Response(200, json={"totalTokens": count})
    workspace = prepare(client)
    result = generate(client, workspace)
    if count == 12001:
        check_error(result, 422, "AI_INPUT_LIMIT", False)
    else:
        check_error(result, 503, "AI_PREFLIGHT_FAILED")
    assert [item.url.path for item in received] == [COUNT]
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.usage is None and row.reserved_cost_usd is None


def test_duplicate_count_keys_cannot_be_coerced(gemini, wire):
    wire[1][COUNT] = lambda _: httpx2.Response(200, content=b'{"totalTokens":1,"totalTokens":2}')
    check_error(generate(gemini[0], prepare(gemini[0])), 503, "AI_PREFLIGHT_FAILED")
    assert len(wire[0]) == 1


@pytest.mark.parametrize("stage", [COUNT, GENERATE])
@pytest.mark.parametrize("defect", ["utf8", "nonstandard-number"])
def test_malformed_wire_body_is_rejected(gemini, wire, capsys, caplog, stage, defect):
    client, engine = gemini
    received, handlers = wire
    if stage == COUNT:
        body = b'{"totalTokens":6000}'
    else:
        output = cited_output()
        if defect == "utf8":
            output["findings"][0]["claim"] = f"{PRIVATE} BYTE_MARKER"
        body = json.dumps(gemini_body(output=output)).encode().replace(b"BYTE_MARKER", b"\xff")
    if defect == "nonstandard-number":
        body = body[:-1] + b',"extra":NaN}'
    elif stage == COUNT:
        body = body[:-1] + b',"extra":"' + PRIVATE.encode() + b' \xff"}'
    handlers[stage] = lambda _: httpx2.Response(
        200, content=body, headers={"content-type": "application/json"}
    )

    workspace = prepare(client)
    with caplog.at_level(logging.DEBUG):
        response = generate(client, workspace)
    (row,) = attempts(engine, workspace)
    if stage == COUNT:
        check_error(response, 503, "AI_PREFLIGHT_FAILED")
        assert row.counted_input_tokens is None and row.reserved_cost_usd is None
        assert [item.url.path for item in received] == [COUNT]
    else:
        check_error(response, 502, "AI_OUTPUT_INVALID")
        assert [item.url.path for item in received] == [COUNT, GENERATE]
    assert row.status == "failed" and row.normalized_output is None
    assert graph_counts(engine, workspace) == [0] * 5
    capture = capsys.readouterr()
    for marker in (PRIVATE, FAKE_KEY, "\ufffd"):
        assert marker not in response.text + caplog.text + capture.out + capture.err + str(
            vars(row)
        )


def test_valid_utf8_is_preserved_under_a_conflicting_charset(gemini, wire):
    output = cited_output()
    claim = "The internal attempt recorded an unknown outcome (résultat inconnu)."
    output["findings"][0]["claim"] = claim
    envelope = gemini_body()
    # The output JSON is nested in a wire JSON string, so encode it with literal UTF-8 too.
    envelope["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(
        output, ensure_ascii=False
    )
    wire[1][GENERATE] = lambda _: httpx2.Response(
        200,
        content=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json; charset=iso-8859-1"},
    )

    client, _ = gemini
    response = generate(client, prepare(client))
    assert response.status_code == 201, response.text
    assert response.json()["findings"][0]["claim"] == claim


@pytest.mark.parametrize(
    "stage,status,code,retryable",
    [
        (COUNT, 401, "AI_CONFIGURATION_ERROR", False),
        (COUNT, 429, "AI_PROVIDER_RATE_LIMITED", True),
        (COUNT, 408, "AI_DEADLINE_EXCEEDED", True),
        (COUNT, 500, "AI_PROVIDER_UNAVAILABLE", True),
        (GENERATE, 400, "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 403, "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 404, "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 307, "AI_PROVIDER_UNAVAILABLE", True),
        (GENERATE, 429, "AI_PROVIDER_RATE_LIMITED", True),
        (GENERATE, 503, "AI_PROVIDER_UNAVAILABLE", True),
        (GENERATE, 504, "AI_DEADLINE_EXCEEDED", True),
    ],
)
def test_upstream_errors_are_safe_and_never_retried(
    gemini, wire, caplog, stage, status, code, retryable
):
    client, engine = gemini
    received, handlers = wire
    handlers[stage] = lambda _: httpx2.Response(
        status,
        json={"error": {"message": f"{PRIVATE} {FAKE_KEY}"}},
        headers={"Retry-After": "0", "Location": "https://redirect.example.invalid"},
    )
    workspace = prepare(client)
    with caplog.at_level(logging.DEBUG):
        response = generate(client, workspace)
    check_error(response, 503, code, retryable)
    assert [item.url.path for item in received] == (
        [COUNT] if stage == COUNT else [COUNT, GENERATE]
    )
    (row,) = attempts(engine, workspace)
    assert row.status == ("interrupted" if code == "AI_DEADLINE_EXCEEDED" else "failed")
    assert row.normalized_output is None and row.provider_response_id is None
    assert row.actual_cost_usd is None and row.usage is None
    for marker in (PRIVATE, FAKE_KEY):
        assert (
            marker not in response.text
            and marker not in caplog.text
            and marker not in str(vars(row))
        )


@pytest.mark.parametrize("stage", [COUNT, GENERATE])
@pytest.mark.parametrize(
    "status,code,retryable,attempt_status",
    [
        (429, "AI_PROVIDER_RATE_LIMITED", True, "failed"),
        (504, "AI_DEADLINE_EXCEEDED", True, "interrupted"),
        (403, "AI_CONFIGURATION_ERROR", False, "failed"),
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        b'{"error":{"message":"' + PRIVATE.encode() + b' \xff"}}',
        b"\xff\xfe",
        b'{"error": {"message": "' + PRIVATE.encode() + b'"',
    ],
    ids=["malformed-utf8-json", "raw-invalid-utf8", "truncated-json"],
)
def test_unsuccessful_responses_with_malformed_bodies_preserve_http_classification(
    gemini, wire, caplog, stage, status, code, retryable, attempt_status, body
):
    client, engine = gemini
    received, handlers = wire
    handlers[stage] = lambda _: httpx2.Response(
        status,
        content=body,
        headers={"content-type": "application/json"},
    )
    workspace = prepare(client)
    with caplog.at_level(logging.DEBUG):
        response = generate(client, workspace)
    check_error(response, 503, code, retryable)
    assert [item.url.path for item in received] == (
        [COUNT] if stage == COUNT else [COUNT, GENERATE]
    )
    (row,) = attempts(engine, workspace)
    assert row.status == attempt_status and row.failure_code == code
    assert row.retryable is retryable
    assert row.normalized_output is None and row.provider_response_id is None
    assert row.returned_model is None and row.actual_cost_usd is None and row.usage is None
    assert (row.counted_input_tokens == 6000) == (stage == GENERATE)
    assert (row.reserved_cost_usd == 0) == (stage == GENERATE)
    assert graph_counts(engine, workspace) == [0] * 5
    for marker in (PRIVATE, FAKE_KEY, "\ufffd"):
        assert (
            marker not in response.text
            and marker not in caplog.text
            and marker not in str(vars(row))
        )


@pytest.mark.parametrize("stage", [COUNT, GENERATE])
def test_outer_timeout_cancels_transport_without_retry(deployment, wire, stage):
    engine, config = deployment
    received, handlers = wire
    cancelled = []

    async def hang(_):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(stage)

    handlers[stage] = hang
    config = config.model_copy(
        update={
            "ai_findings_count_timeout_seconds": 0.025,
            "ai_findings_model_timeout_seconds": 0.025,
        }
    )
    with worker(config) as client:
        bootstrap(client)
        workspace = prepare(client)
        check_error(generate(client, workspace), 503, "AI_DEADLINE_EXCEEDED")
    assert cancelled == [stage]
    assert [item.url.path for item in received] == (
        [COUNT] if stage == COUNT else [COUNT, GENERATE]
    )
    (row,) = attempts(engine, workspace)
    assert row.status == "interrupted" and row.usage is None


def test_connection_error_is_not_retried_or_fallen_back(gemini, wire):
    def disconnected(request):
        raise httpx2.ConnectError(PRIVATE, request=request)

    wire[1][GENERATE] = disconnected
    check_error(generate(gemini[0], prepare(gemini[0])), 503, "AI_PROVIDER_UNAVAILABLE")
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


@pytest.mark.parametrize(
    "finish,part",
    [
        ("STOP", {"thought": True, "text": {"bad": PRIVATE}}),
        ("STOP", {"thought": True, "text": None, "thoughtSignature": PRIVATE}),
        ("STOP", {"thought": True}),
        ("STOP", {"thoughtSignature": ""}),
        ("STOP", {"thought": "true", "text": PRIVATE}),
        ("STOP", {"thought": True, "text": PRIVATE, "thoughtSignature": {"bad": PRIVATE}}),
        ("STOP", {"thought": True, "text": PRIVATE, "inlineData": {"data": PRIVATE}}),
        ("MAX_TOKENS", {"thought": True, "text": {"bad": PRIVATE}}),
        ("RECITATION", {"thought": True, "text": {"bad": PRIVATE}}),
    ],
)
def test_parts_must_be_structurally_valid_before_discarding_thoughts(
    gemini, wire, caplog, finish, part
):
    body = gemini_body(finish=finish)
    body["candidates"][0]["content"]["parts"].insert(0, part)
    wire[1][GENERATE] = lambda _: httpx2.Response(200, json=body)
    client, engine = gemini
    workspace = prepare(client)
    with caplog.at_level(logging.DEBUG):
        response = generate(client, workspace)
    check_error(response, 502, "AI_OUTPUT_INVALID")
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.normalized_output is None
    assert graph_counts(engine, workspace) == [0] * 5
    assert PRIVATE not in response.text + caplog.text + str(vars(row))


@pytest.mark.parametrize(
    "scenario,code,status,retryable",
    [
        ("blocked", "AI_REFUSED", 422, False),
        ("recitation", "AI_REFUSED", 422, False),
        ("truncated", "AI_OUTPUT_INCOMPLETE", 502, True),
        ("continuation", "AI_OUTPUT_INCOMPLETE", 502, True),
        ("contradictory-continuation", "AI_OUTPUT_INVALID", 502, True),
        ("contradictory-empty-continuation", "AI_OUTPUT_INVALID", 502, True),
        ("no-candidate", "AI_OUTPUT_INVALID", 502, True),
        ("two-candidates", "AI_OUTPUT_INVALID", 502, True),
        ("function-call", "AI_OUTPUT_INVALID", 502, True),
        ("unknown-finish", "AI_OUTPUT_INVALID", 502, True),
        ("malformed-envelope", "AI_OUTPUT_INVALID", 502, True),
        ("duplicate-envelope", "AI_OUTPUT_INVALID", 502, True),
        ("bad-json", "AI_OUTPUT_INVALID", 502, True),
        ("duplicate-json", "AI_OUTPUT_INVALID", 502, True),
        ("long-claim", "AI_OUTPUT_INVALID", 502, True),
        ("bad-local-id", "AI_OUTPUT_INVALID", 502, True),
        ("unexpected-field", "AI_OUTPUT_INVALID", 502, True),
        ("missing-model", "AI_OUTPUT_INVALID", 502, True),
        ("malformed-model", "AI_OUTPUT_INVALID", 502, True),
        ("model-alias", "AI_CONFIGURATION_ERROR", 503, False),
        ("unreturned-record", "AI_REFERENCE_INVALID", 502, True),
        ("nonexistent-pointer", "AI_REFERENCE_INVALID", 502, True),
        ("bad-citation-index", "AI_REFERENCE_INVALID", 502, True),
        ("reported-input-over-limit", "AI_INPUT_LIMIT", 422, False),
        ("leaked-key", "AI_OUTPUT_INVALID", 502, True),
    ],
)
def test_response_rejection_is_atomic(gemini, wire, scenario, code, status, retryable):
    output = cited_output()
    finding = output["findings"][0]
    body = gemini_body()
    (candidate,) = body["candidates"]
    parts = candidate["content"]["parts"]
    match scenario:
        case "blocked":
            body = {"promptFeedback": {"blockReason": "SAFETY", "blockReasonMessage": PRIVATE}}
        case "recitation":
            candidate["finishReason"] = "RECITATION"
            candidate.pop("content")
        case "truncated":
            candidate["finishReason"] = "MAX_TOKENS"
        case "continuation":
            candidate.update(finishReason="CONTINUATION", continuationToken="b2ZmbGluZQ==")
        case "contradictory-continuation":
            candidate.update(finishReason="STOP", continuationToken="Y29udGludWU=")
        case "contradictory-empty-continuation":
            candidate.update(finishReason="STOP", continuationToken="")
        case "no-candidate":
            body.pop("candidates")
        case "two-candidates":
            body["candidates"].append(candidate | {"index": 1})
        case "function-call":
            parts.append({"functionCall": {"name": "should_not_be_called", "args": {}}})
        case "unknown-finish":
            candidate["finishReason"] = "UNEXPECTED_TOOL_CALL"
        case "malformed-envelope":
            candidate["content"] = []
        case "duplicate-envelope":
            body = json.dumps(body).replace(
                '"finishReason":', '"finishReason":"STOP","finishReason":'
            )
        case "bad-json":
            parts[0]["text"] = '{"findings": ' + PRIVATE
        case "duplicate-json":
            parts[0]["text"] = '{"findings": [],' + json.dumps(output)[1:]
        case "long-claim":
            finding["claim"] = "a" * 241
            body = gemini_body(output=output)
        case "bad-local-id":
            finding["citations"][0]["evidence_record_id"] = "invalid path/with spaces"
            body = gemini_body(output=output)
        case "unexpected-field":
            finding["review_state"] = "accepted"
            body = gemini_body(output=output)
        case "missing-model":
            body.pop("modelVersion")
        case "malformed-model":
            body["modelVersion"] = [MODEL]
        case "model-alias":
            body["modelVersion"] = f"{MODEL}-other-version"
        case "unreturned-record":
            finding["citations"][0]["evidence_record_id"] = "SYN-PO-ATT-002-A"
            body = gemini_body(output=output)
        case "nonexistent-pointer":
            finding["citations"][0]["pointer"] = "/payload/Unknown field"
            body = gemini_body(output=output)
        case "bad-citation-index":
            finding["rationale"][0]["citation_indexes"] = [1]
            body = gemini_body(output=output)
        case "reported-input-over-limit":
            body["usageMetadata"].update(promptTokenCount=12001, totalTokenCount=12408)
        case "leaked-key":
            finding["claim"] = FAKE_KEY
            body = gemini_body(output=output, responseId=FAKE_KEY)
            # The decoded finding still contains a key when the output JSON uses escapes.
            body["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(output).replace(
                FAKE_KEY, r"\u0067" + FAKE_KEY[1:]
            )
    wire[1][GENERATE] = lambda _: (
        httpx2.Response(200, content=body)
        if isinstance(body, str)
        else httpx2.Response(200, json=body)
    )
    client, engine = gemini
    workspace = prepare(client)
    response = generate(client, workspace)
    check_error(response, status, code, retryable)
    assert PRIVATE not in response.text and FAKE_KEY not in response.text
    (row,) = attempts(engine, workspace)
    assert row.normalized_output is None and row.failure_code == code and row.status == "failed"
    assert PRIVATE not in str(vars(row)) and FAKE_KEY not in str(vars(row))
    assert graph_counts(engine, workspace) == [0] * 5
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


def test_contradictory_continuation_preserves_slot_and_accounting_for_manual_retry(
    deployment, wire, database_clock
):
    engine, config = deployment
    received, handlers = wire
    body = gemini_body()
    body["candidates"][0]["continuationToken"] = "Y29udGludWU="
    handlers[GENERATE] = lambda _: httpx2.Response(200, json=body)

    with worker(config, database_clock) as client:
        bootstrap(client)
        workspace = prepare(client)
        initial = check_error(generate(client, workspace), 502, "AI_OUTPUT_INVALID")
        assert [item.url.path for item in received] == [COUNT, GENERATE]
        assert graph_counts(engine, workspace) == [0] * 5
        (first,) = attempts(engine, workspace)
        assert first.status == "failed" and first.failure_code == "AI_OUTPUT_INVALID"
        assert first.retryable is True and first.normalized_output is None
        assert first.counted_input_tokens == 6000 and first.reserved_cost_usd == 0
        assert (
            first.returned_model
            is first.provider_response_id
            is first.usage
            is first.actual_cost_usd
            is None
        )

        retry = {
            "expected_draft_version": initial["draft_version"],
            "retry_of_generation_id": initial["generation_id"],
        }
        check_error(generate(client, workspace, **retry), 429, "AI_LOCAL_RATE_LIMITED")
        assert [item.url.path for item in received] == [COUNT, GENERATE]

        database_clock.now += timedelta(seconds=60)
        handlers[GENERATE] = lambda _: httpx2.Response(200, json=gemini_body())
        retried = generate(client, workspace, **retry)
        assert retried.status_code == 201, retried.text
        assert [item.url.path for item in received] == [COUNT, GENERATE, COUNT, GENERATE]
        assert graph_counts(engine, workspace) == [1, 1, 1, 1, 0]
        first, second = attempts(engine, workspace)
        assert first.status == "failed" and second.status == "completed"
        assert second.retry_of_generation_id == first.generation_id
        assert second.usage == {
            "input_tokens": 6001,
            "output_tokens": 407,
            "total_tokens": 6408,
            "cached_input_tokens": 4,
            "reasoning_tokens": 7,
        }


@pytest.mark.parametrize(
    "usage_update",
    [
        None,
        {"promptTokenCount": True},
        {"promptTokenCount": "6001"},
        {"candidatesTokenCount": None},
        {"totalTokenCount": 6409},
        {"cachedContentTokenCount": 6002},
        {"thoughtsTokenCount": -1},
        {"toolUsePromptTokenCount": 1},
    ],
)
def test_untrustworthy_usage_remains_unknown(gemini, wire, usage_update):
    body = gemini_body(responseId=f"{PRIVATE} invalid ID")
    if usage_update is None:
        body.pop("usageMetadata")
    else:
        body["usageMetadata"].update(usage_update)
    wire[1][GENERATE] = lambda _: httpx2.Response(200, json=body)
    client, engine = gemini
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 201, response.text
    (row,) = attempts(engine, workspace)
    assert (
        row.returned_model == MODEL
        and row.usage is row.actual_cost_usd is row.provider_response_id is None
    )
    assert response.json()["generation_history"][0]["usage"] is None


def test_usage_with_omitted_optional_counters(gemini, wire):
    body = gemini_body(
        output=EMPTY,
        usageMetadata={
            "promptTokenCount": 6001,
            "candidatesTokenCount": 23,
            "totalTokenCount": 6024,
        },
    )
    wire[1][GENERATE] = lambda _: httpx2.Response(200, json=body)
    client, engine = gemini
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 201, response.text
    assert response.json()["no_findings_reason"] == "no_assessable_claims"
    assert response.json()["generation_history"][0]["usage"] == {
        "input_tokens": 6001,
        "output_tokens": 23,
        "total_tokens": 6024,
    }
    assert graph_counts(engine, workspace) == [0] * 5
    check_error(
        generate(client, workspace | {"draft_version": 4}), 409, "FINDINGS_ALREADY_GENERATED", False
    )
    assert len(wire[0]) == 2


def test_duplicate_usage_key_is_unknown_without_invalidating_the_finding(gemini, wire):
    body = json.dumps(gemini_body()).replace(
        '"promptTokenCount":', '"promptTokenCount":0, "promptTokenCount":'
    )
    wire[1][GENERATE] = lambda _: httpx2.Response(200, content=body)
    client, engine = gemini
    workspace = prepare(client)
    response = generate(client, workspace)
    assert response.status_code == 201, response.text
    assert attempts(engine, workspace)[0].usage is None


@pytest.fixture
def database_clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(
        findings.func, "clock_timestamp", lambda: literal(clock.now, type_=DateTime(timezone=True))
    )
    return clock


def seed_attempt(db, workspace, requested, *, status="failed", deadline=None, provider="gemini"):
    generation_id = uuid4()
    db.add(
        AIGenerationRequest(
            state_id=UUID(workspace["state_id"]),
            generation_id=generation_id,
            thread_kind="payment_failures",
            case_id="case-failure-001",
            evidence_request_id=UUID(workspace["evidence_request_id"]),
            status=status,
            requested_at=requested,
            deadline_at=deadline or requested + timedelta(seconds=20),
            finished_at=None if status == "pending" else requested + timedelta(seconds=1),
            expected_draft_version=2,
            post_start_version=3,
            retryable=True,
            provider=provider,
            configured_model="historical-model",
            prompt_version="findings-v1",
            schema_version="task5.v1",
            input_bundle={},
            input_digest="0" * 64,
            budget={},
        )
    )
    return generation_id


def test_competing_workers_share_fifth_slot_and_restart_keeps_limit(
    deployment, wire, database_clock, monkeypatch
):
    engine, config = deployment
    with (
        worker(config, database_clock) as first,
        worker(config, database_clock) as second,
        worker(config, database_clock) as earlier,
    ):
        assert first.app.state.engine is not second.app.state.engine
        first.app.state.engine.update_execution_options(isolation_level="REPEATABLE READ")
        bootstrap(first)
        bootstrap(second)
        bootstrap(earlier)
        one, two = prepare(first), prepare(second)
        history = prepare(earlier)
        assert one["investigation_id"] != two["investigation_id"]
        with Session(engine) as db, db.begin():
            for minutes, status in enumerate(
                ("failed", "interrupted", "stale", "pending"), start=2
            ):
                seed_attempt(
                    db, history, database_clock.now - timedelta(minutes=minutes), status=status
                )
        arrivals = Barrier(2, timeout=5)
        observed = []
        admit = findings.gemini_admission_time

        def race(db):
            observed.append(
                (db.scalar(select(func.pg_backend_pid())), db.connection().get_isolation_level())
            )
            arrivals.wait()
            return admit(db)

        with monkeypatch.context() as race_patch, ThreadPoolExecutor(max_workers=2) as pool:
            race_patch.setattr(findings, "gemini_admission_time", race)
            first_request = pool.submit(generate, first, one)
            second_request = pool.submit(generate, second, two)
            responses = [first_request.result(timeout=10), second_request.result(timeout=10)]
        assert len({pid for pid, _ in observed}) == 2
        assert {level for _, level in observed} == {"READ COMMITTED"}
        assert sorted(result.status_code for result in responses) == [201, 429]
        rejected = next(result for result in responses if result.status_code == 429)
        assert check_error(rejected, 429, "AI_LOCAL_RATE_LIMITED") == {}
        assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]
        with Session(engine) as db:
            rows = db.scalars(select(AIGenerationRequest)).all()
            assert len(rows) == 5
            latest = max(rows, key=lambda row: row.requested_at)
            assert latest.requested_at == database_clock.now and latest.status == "completed"

    database_clock.now += timedelta(seconds=61)
    with worker(config, database_clock) as restarted:
        bootstrap(restarted)
        three = prepare(restarted)
        assert three["investigation_id"] not in {one["investigation_id"], two["investigation_id"]}
        assert check_error(generate(restarted, three), 429, "AI_LOCAL_RATE_LIMITED") == {}
        assert attempts(engine, three) == []
        assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


@pytest.mark.parametrize(
    "window,age_offset,allowed",
    [
        ("minute", -1, False),
        ("minute", 0, True),
        ("day", -1, False),
        ("day", 0, True),
        ("pending", -1, False),
        ("pending", 0, True),
    ],
)
def test_exact_elapsed_admission_boundaries(
    deployment, wire, database_clock, window, age_offset, allowed
):
    engine, config = deployment
    with worker(config, database_clock) as earlier, worker(config, database_clock) as next_worker:
        bootstrap(earlier)
        bootstrap(next_worker)
        other_scope, target = prepare(earlier), prepare(next_worker)
        now = database_clock.now
        delta = timedelta(microseconds=age_offset)
        with Session(engine) as db, db.begin():
            if window == "day":
                for minutes in range(2, 6):
                    seed_attempt(db, other_scope, now - timedelta(minutes=minutes))
                seed_attempt(db, other_scope, now - timedelta(hours=24) - delta)
            elif window == "minute":
                seed_attempt(db, other_scope, now - timedelta(minutes=1) - delta)
            else:
                seed_attempt(
                    db,
                    other_scope,
                    now - timedelta(hours=25),
                    status="pending",
                    deadline=now - delta,
                )
            # A recent non-Gemini row belongs to an independent provider policy.
            seed_attempt(db, other_scope, now, provider="openai")
        response = generate(next_worker, target)
        if allowed:
            assert response.status_code == 201, response.text
            assert attempts(engine, target)[0].requested_at == now
        else:
            assert check_error(response, 429, "AI_LOCAL_RATE_LIMITED") == {}
            assert attempts(engine, target) == []
        assert [item.url.path for item in wire[0]] == ([COUNT, GENERATE] if allowed else [])


def test_local_lock_contention_denies_without_waiting_or_dispatch(gemini, wire):
    client, engine = gemini
    workspace = prepare(client)
    with engine.begin() as lock_holder:
        assert lock_holder.scalar(
            select(func.pg_try_advisory_xact_lock(*findings.GEMINI_ADMISSION_LOCK))
        )
        assert check_error(generate(client, workspace), 429, "AI_LOCAL_RATE_LIMITED") == {}
        assert attempts(engine, workspace) == [] and wire[0] == []
    assert generate(client, workspace).status_code == 201


def test_daily_window_uses_elapsed_hours_across_a_database_timezone_change(gemini, database_clock):
    client, engine = gemini
    workspace = prepare(client)
    # New York jumps forward an hour during this UTC window.
    database_clock.now = datetime(2026, 3, 8, 16, tzinfo=UTC)
    with Session(engine) as db, db.begin():
        for minutes in range(2, 6):
            seed_attempt(db, workspace, database_clock.now - timedelta(minutes=minutes))
        seed_attempt(db, workspace, database_clock.now - timedelta(hours=23, minutes=30))
    with Session(engine) as db, db.begin():
        db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        assert db.scalar(select(func.clock_timestamp())).utcoffset() == timedelta(hours=-4)
        with pytest.raises(findings.GenerationFailure) as denied:
            findings.gemini_admission_time(db)
        assert denied.value.code == "AI_LOCAL_RATE_LIMITED"


def test_crash_before_dispatch_is_counted_and_recovered_after_restart(
    deployment, wire, database_clock
):
    engine, config = deployment
    with worker(config, database_clock) as initial:
        bootstrap(initial)
        workspace = prepare(initial)
        attempt = findings.start(
            SimpleNamespace(app=initial.app, cookies=initial.cookies),
            UUID(workspace["investigation_id"]),
            "payment_failures",
            "case-failure-001",
            FindingGenerationCreate(
                state_id=UUID(workspace["state_id"]),
                expected_draft_version=workspace["draft_version"],
                evidence_request_id=UUID(workspace["evidence_request_id"]),
            ),
            database_clock,
        )
        assert attempts(engine, workspace)[0].generation_id == attempt.generation_id
        assert wire[0] == []
    database_clock.now += timedelta(seconds=25)
    with worker(config, database_clock) as restarted, worker(config, database_clock) as different:
        restarted.cookies.update(initial.cookies)
        bootstrap(different)
        other = prepare(different)
        stored = read(restarted, workspace)
        assert stored.status_code == 200
        assert stored.json()["generation_status"] == "interrupted"
        assert stored.json()["generation_history"][0]["failure_code"] == "AI_INTERRUPTED"
        check_error(generate(different, other), 429, "AI_LOCAL_RATE_LIMITED")
        assert wire[0] == []
        (row,) = attempts(engine, workspace)
        assert row.status == "interrupted" and row.counted_input_tokens is None
        database_clock.now += timedelta(seconds=35)
        assert generate(different, other).status_code == 201
        assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


@pytest.mark.parametrize(
    "fail_stage,statement_fragment",
    [
        ("admission-query", "count(*) FILTER"),
        ("after-insert", ".ai_generation_requests ("),
    ],
)
def test_start_database_failure_uses_no_slot_and_sends_no_request(
    gemini, wire, fail_stage, statement_fragment
):
    client, engine = gemini
    workspace = prepare(client)
    worker_engine = client.app.state.engine

    def fail_after_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement_fragment in statement and (
            fail_stage == "admission-query" or statement.startswith("INSERT")
        ):
            raise OperationalError(None, None, RuntimeError(PRIVATE))

    event.listen(worker_engine, "after_cursor_execute", fail_after_statement)
    try:
        response = generate(client, workspace)
    finally:
        event.remove(worker_engine, "after_cursor_execute", fail_after_statement)
    check_error(response, 503, "DATABASE_UNAVAILABLE")
    assert PRIVATE not in response.text
    assert attempts(engine, workspace) == [] and wire[0] == []
    assert read(client, workspace).json()["draft_version"] == workspace["draft_version"]
    assert generate(client, workspace).status_code == 201
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


def test_provider_rate_limit_consumes_pacing_slot_and_manual_retry_links_history(
    deployment, wire, database_clock
):
    engine, config = deployment
    received, handlers = wire
    handlers[COUNT] = lambda _: httpx2.Response(429, json={"error": {"message": PRIVATE}})
    with (
        worker(config, database_clock) as client,
        worker(config, database_clock) as another_visitor,
    ):
        bootstrap(client)
        bootstrap(another_visitor)
        workspace, other = prepare(client), prepare(another_visitor)
        initial = check_error(generate(client, workspace), 503, "AI_PROVIDER_RATE_LIMITED")
        check_error(generate(another_visitor, other), 429, "AI_LOCAL_RATE_LIMITED")
        assert attempts(engine, other) == []
        assert [item.url.path for item in received] == [COUNT]
        retry = {
            "expected_draft_version": initial["draft_version"],
            "retry_of_generation_id": initial["generation_id"],
        }
        check_error(generate(client, workspace, **retry), 429, "AI_LOCAL_RATE_LIMITED")
        database_clock.now += timedelta(seconds=60)
        handlers[COUNT] = lambda _: httpx2.Response(200, json={"totalTokens": 6000})
        assert generate(client, workspace, **retry).status_code == 201
        first, second = attempts(engine, workspace)
        assert first.status == "failed" and second.status == "completed"
        assert second.retry_of_generation_id == first.generation_id
        assert [item.url.path for item in received] == [COUNT, COUNT, GENERATE]


def test_visitor_authorization_and_stale_version_precede_admission(deployment, wire):
    engine, config = deployment
    with worker(config) as owner, worker(config) as stranger:
        bootstrap(owner)
        workspace = prepare(owner)
        check_error(generate(stranger, workspace), 401, "SESSION_REQUIRED", False)
        bootstrap(stranger)
        check_error(generate(stranger, workspace), 404, "NOT_FOUND", False)
        check_error(
            generate(owner, workspace, expected_draft_version=0), 409, "STALE_DRAFT_VERSION", False
        )
        assert attempts(engine, workspace) == [] and wire[0] == []


def test_session_expiry_after_count_prevents_generation_and_publication(
    deployment, wire, database_clock
):
    engine, config = deployment
    config = config.model_copy(update={"visitor_session_ttl_seconds": 8})
    with worker(config, database_clock) as client:
        bootstrap(client)
        workspace = prepare(client)

        def expire_session(_):
            database_clock.now += timedelta(seconds=8)
            return httpx2.Response(200, json={"totalTokens": 6000})

        wire[1][COUNT] = expire_session
        check_error(generate(client, workspace), 401, "SESSION_EXPIRED", False)
    (row,) = attempts(engine, workspace)
    assert row.status == "pending" and row.counted_input_tokens is None
    assert graph_counts(engine, workspace) == [0] * 5
    assert [item.url.path for item in wire[0]] == [COUNT]


def test_stale_version_after_generate_cannot_publish(gemini, wire):
    client, engine = gemini
    workspace = prepare(client)

    def move_draft(_):
        with Session(engine) as db, db.begin():
            draft = db.get(WorkingDraft, UUID(workspace["investigation_id"]))
            draft.draft_version += 1
        return httpx2.Response(200, json=gemini_body())

    wire[1][GENERATE] = move_draft
    check_error(generate(client, workspace), 409, "STALE_DRAFT_VERSION", False)
    assert graph_counts(engine, workspace) == [0] * 5
    assert attempts(engine, workspace)[0].status == "stale"
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


def test_publication_failure_rolls_back_the_graph_and_leaves_start_recoverable(
    deployment, wire, database_clock
):
    engine, config = deployment
    with worker(config, database_clock) as client:
        bootstrap(client)
        workspace = prepare(client)
        worker_engine = client.app.state.engine

        def fail_publication(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.startswith("INSERT") and ".evidence_citations (" in statement:
                raise OperationalError(None, None, RuntimeError(PRIVATE))

        event.listen(worker_engine, "after_cursor_execute", fail_publication)
        try:
            check_error(generate(client, workspace), 503, "DATABASE_UNAVAILABLE")
        finally:
            event.remove(worker_engine, "after_cursor_execute", fail_publication)
        assert graph_counts(engine, workspace) == [0] * 5
        assert attempts(engine, workspace)[0].status == "pending"
        database_clock.now += timedelta(seconds=21)
        assert read(client, workspace).json()["generation_status"] == "interrupted"
        assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


def test_gemini_pending_fences_evidence_retrieval(gemini, wire):
    client, engine = gemini
    workspace = prepare(client)

    async def attempt_retrieval(_):
        blocked = await asyncio.to_thread(
            retrieve, client, workspace | {"draft_version": workspace["draft_version"] + 1}
        )
        check_error(blocked, 409, "OPERATION_IN_PROGRESS", False)
        assert attempts(engine, workspace)[0].status == "pending"
        return httpx2.Response(200, json=gemini_body())

    wire[1][GENERATE] = attempt_retrieval
    assert generate(client, workspace).status_code == 201
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]


@pytest.mark.parametrize("partial_stripe", [False, True])
def test_replays_duplicate_case_and_preserves_partial_evidence(
    gemini, wire, monkeypatch, partial_stripe
):
    client, _ = gemini
    thread, case = "possible_duplicates", "case-duplicate-001"
    if partial_stripe:
        read_source = evidence.read_source

        def fail_stripe(request, criteria, source_key, inventory, end):
            if source_key == "stripe":
                raise RuntimeError("Synthetic Stripe retrieval failure")
            return read_source(request, criteria, source_key, inventory, end)

        monkeypatch.setattr(evidence, "read_source", fail_stripe)

    async def replay(request):
        payload = json.loads(request.content)
        text = payload["contents"][0]["parts"][0]["text"]
        selected = json.loads(text.split("\n", 1)[1]) | {
            "response_options": {
                "max_output_tokens": payload["generationConfig"]["maxOutputTokens"]
            }
        }
        curated = await MockFindingsProvider().generate(selected, timeout=1)
        return httpx2.Response(200, json=gemini_body(output=json.loads(curated.output_json)))

    wire[1][GENERATE] = replay
    response = generate(client, prepare(client, thread, case), thread, case)
    assert response.status_code == 201, response.text
    body = response.json()
    assert all(item["review_state"] == "awaiting_review" for item in body["findings"])
    outcomes = {item["source_key"]: item for item in body["source_outcomes"]}
    assert len(outcomes) == 6
    states = {item["claim"]: item["proposed_status"] for item in body["findings"]}
    attempts_claim = (
        "Two distinct internal attempt records share candidate customer/order and amount context."
    )
    assert states[attempts_claim] == "confirmed"
    if partial_stripe:
        assert outcomes["stripe"]["execution_status"] == "failed"
        assert outcomes["stripe"]["returned_count"] is None
        assert all(
            item["evidence_record_id"] != "SYN-STRIPE-DUP-001" for item in body["cited_records"]
        )
        assert outcomes["loki"]["match_status"] == outcomes["tempo"]["match_status"] == "no_matches"
        assert "inconclusive" in states.values()
    else:
        assert (
            states["The returned provider extract contains two distinct capture references."]
            == "not_confirmed"
        )
        assert states["The customer's bank posted two debits."] == "inconclusive"


@pytest.mark.parametrize(
    "stage,http_status,upstream_status,api_code,retryable",
    [
        (GENERATE, 400, "INVALID_ARGUMENT", "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 401, "UNAUTHENTICATED", "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 403, "PERMISSION_DENIED", "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 404, "NOT_FOUND", "AI_CONFIGURATION_ERROR", False),
        (GENERATE, 429, "RESOURCE_EXHAUSTED", "AI_PROVIDER_RATE_LIMITED", True),
        (COUNT, 400, "INVALID_ARGUMENT", "AI_CONFIGURATION_ERROR", False),
        (COUNT, 429, "RESOURCE_EXHAUSTED", "AI_PROVIDER_RATE_LIMITED", True),
    ],
)
def test_upstream_http_diagnostics_log_allowlisted_status_without_leaking_secrets(
    deployment,
    monkeypatch,
    capsys,
    caplog,
    stage,
    http_status,
    upstream_status,
    api_code,
    retryable,
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    secret_header = f"secret-header-{PRIVATE}"
    handlers[stage] = lambda _: httpx2.Response(
        http_status,
        json={
            "error": {
                "code": http_status,
                "message": f"Upstream error details {PRIVATE} {SYNTHETIC_AQ_KEY}",
                "status": upstream_status,
                "details": [{"reason": PRIVATE}],
            }
        },
        headers={
            "Set-Cookie": f"session={secret_header}; HttpOnly",
            "X-Debug-Token": secret_header,
        },
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, api_code, retryable)
        assert [item.url.path for item in received] == (
            [COUNT] if stage == COUNT else [COUNT, GENERATE]
        )

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == api_code
    expected_operation = "count_tokens" if stage == COUNT else "generate_content"
    diagnostic_lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.gemini_findings_provider"
    ]
    assert diagnostic_lines == [
        f"Gemini diagnostic: category=upstream_http_error operation={expected_operation} "
        f"http_status={http_status} upstream_error_status={upstream_status}"
    ]
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, secret_header, "Upstream error details", "X-Debug"):
        assert marker not in caplog.text
        assert marker not in response.text
        assert marker not in capture.out + capture.err
        assert marker not in str(vars(row))


@pytest.mark.parametrize(
    "body",
    [
        json.dumps(
            {
                "error": {
                    "code": 400,
                    "message": f"{PRIVATE} {SYNTHETIC_AQ_KEY}",
                    "status": f"UNLISTED_{PRIVATE}_{SYNTHETIC_AQ_KEY}",
                }
            }
        ).encode(),
        json.dumps({"error": {"code": 400, "message": PRIVATE, "status": 400}}).encode(),
        (
            b'{"error":{"status":"INVALID_ARGUMENT","status":"NOT_FOUND","message":"'
            + PRIVATE.encode()
            + b'"}}'
        ),
        (
            b'{"error":{"status":"INVALID_ARGUMENT","message":"'
            + PRIVATE.encode()
            + b" "
            + (b"x" * 70000)
            + b'"}}'
        ),
        (b'{"error":{"status":"INVALID_ARGUMENT","message":"' + PRIVATE.encode() + b' \xff"}}'),
    ],
    ids=[
        "unknown-error-status",
        "non-string-error-status",
        "duplicate-error-status-keys",
        "oversized-error-body",
        "malformed-utf8-error-body",
    ],
)
def test_upstream_http_diagnostics_omit_non_allowlisted_or_malformed_error_statuses(
    deployment, monkeypatch, capsys, caplog, body
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    handlers[GENERATE] = lambda _: httpx2.Response(
        400,
        content=body,
        headers={"content-type": "application/json", "X-Leak": PRIVATE},
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    diagnostic_lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.gemini_findings_provider"
    ]
    assert diagnostic_lines == [
        "Gemini diagnostic: category=upstream_http_error operation=generate_content http_status=400"
    ]
    assert "upstream_error_status=" not in caplog.text
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "UNLISTED", "\ufffd", "X-Leak"):
        assert marker not in caplog.text
        assert marker not in response.text
        assert marker not in capture.out + capture.err
        assert marker not in str(vars(row))


def test_model_version_mismatch_logs_diagnostic_without_leaking_model_or_body(
    deployment, monkeypatch, capsys, caplog
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    mismatched_model = f"{MODEL}-canary-{PRIVATE}-{SYNTHETIC_AQ_KEY}"
    output = cited_output()
    output["findings"][0]["claim"] = f"Claim containing {PRIVATE}"
    handlers[GENERATE] = lambda _: httpx2.Response(
        200,
        json=gemini_body(output=output, modelVersion=mismatched_model, responseId=PRIVATE),
        headers={"Set-Cookie": f"vendor={PRIVATE}", "X-Model-Header": PRIVATE},
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    assert row.returned_model is None and row.normalized_output is None
    assert graph_counts(engine, workspace) == [0] * 5
    diagnostic_lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.gemini_findings_provider"
    ]
    assert diagnostic_lines == [
        "Gemini diagnostic: category=model_version_mismatch "
        "operation=generate_content http_status=200"
    ]
    for marker in (mismatched_model, PRIVATE, SYNTHETIC_AQ_KEY, "canary", "X-Model-Header"):
        assert marker not in caplog.text
        assert marker not in response.text
        assert marker not in capture.out + capture.err
        assert marker not in str(vars(row))


@pytest.mark.parametrize(
    "method,url,expected_reason",
    [
        ("GET", f"{API_ORIGIN}{GENERATE}", "unexpected_method"),
        (
            "POST",
            f"{API_ORIGIN}{GENERATE}?key={SYNTHETIC_AQ_KEY}&note={PRIVATE}",
            "unexpected_url",
        ),
        (
            "POST",
            f"https://unexpected.example.invalid/v1/models/{MODEL}:generateContent?token={PRIVATE}",
            "unexpected_url",
        ),
    ],
    ids=["unexpected-method", "unexpected-query-with-secret", "unexpected-origin"],
)
def test_local_request_guard_rejection_logs_category_without_url_or_secrets(
    caplog, capsys, method, url, expected_reason
):
    request = httpx2.Request(
        method,
        url,
        headers={
            "x-goog-api-key": SYNTHETIC_AQ_KEY,
            "cookie": f"session={PRIVATE}",
        },
        content=json.dumps({"sensitive_body": PRIVATE}).encode(),
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ProviderFailure) as exc_info:
            asyncio.run(guard_request(request))
    assert exc_info.value.kind == "configuration"
    capture = capsys.readouterr()
    diagnostic_lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.gemini_findings_provider"
    ]
    assert diagnostic_lines == [
        f"Gemini diagnostic: category=local_request_guard reason={expected_reason}"
    ]
    for marker in (
        SYNTHETIC_AQ_KEY,
        PRIVATE,
        url,
        "unexpected.example.invalid",
        "x-goog-api-key",
        "sensitive_body",
        ":generateContent",
    ):
        assert marker not in caplog.text
        assert marker not in capture.out + capture.err


class ScriptedAsyncByteStream(httpx2.AsyncByteStream):
    def __init__(self, chunks, *, fail_with: Exception | None = None):
        self.chunks = list(chunks)
        self.fail_with = fail_with
        self.yielded = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk
        if self.fail_with is not None:
            raise self.fail_with

    async def aclose(self):
        self.closed = True


def gemini_diagnostics(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.gemini_findings_provider"
    ]


def test_upstream_error_stream_exact_65536_bytes_extracts_status_and_closes(
    deployment, monkeypatch, capsys, caplog
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    prefix = (
        f'{{"error":{{"status":"INVALID_ARGUMENT","message":"{PRIVATE} {SYNTHETIC_AQ_KEY} '
    ).encode()
    suffix = b'"}}'
    pad_len = MAX_ERROR_BODY_BYTES - len(prefix) - len(suffix)
    assert pad_len > 0
    payload = prefix + (b"a" * pad_len) + suffix
    assert len(payload) == MAX_ERROR_BODY_BYTES == 65536
    stream = ScriptedAsyncByteStream([payload[:20000], payload[20000:45000], payload[45000:]])
    handlers[GENERATE] = lambda _: httpx2.Response(
        400,
        stream=stream,
        headers={"content-type": "application/json", "X-Secret": PRIVATE},
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert stream.closed and stream.yielded == 3
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    assert gemini_diagnostics(caplog) == [
        "Gemini diagnostic: category=upstream_http_error operation=generate_content "
        "http_status=400 upstream_error_status=INVALID_ARGUMENT"
    ]
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "X-Secret"):
        assert marker not in caplog.text + response.text + capture.out + capture.err + str(
            vars(row)
        )


def test_upstream_error_stream_over_limit_cuts_off_early_and_closes(
    deployment, monkeypatch, capsys, caplog
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    prefix = (
        f'{{"error":{{"status":"INVALID_ARGUMENT","message":"{PRIVATE} {SYNTHETIC_AQ_KEY} '
    ).encode()
    filler = b"x" * (MAX_ERROR_BODY_BYTES - len(prefix))
    assert len(prefix) + len(filler) == MAX_ERROR_BODY_BYTES
    stream = ScriptedAsyncByteStream(
        [
            prefix,
            filler,
            b"z",
            b'trailing-sentinel-must-not-be-read"}}',
        ]
    )
    handlers[GENERATE] = lambda _: httpx2.Response(
        400,
        stream=stream,
        headers={"content-type": "application/json"},
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert stream.closed and stream.yielded == 3
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    assert gemini_diagnostics(caplog) == [
        "Gemini diagnostic: category=upstream_http_error operation=generate_content http_status=400"
    ]
    assert "upstream_error_status=" not in caplog.text
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "trailing-sentinel"):
        assert marker not in caplog.text + response.text + capture.out + capture.err + str(
            vars(row)
        )


def test_upstream_error_stream_with_split_utf8_decodes_safely(
    deployment, monkeypatch, capsys, caplog
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    raw = json.dumps(
        {
            "error": {
                "status": "PERMISSION_DENIED",
                "message": f"Denied café € {PRIVATE} {SYNTHETIC_AQ_KEY}",
            }
        },
        ensure_ascii=False,
    ).encode("utf-8")
    euro_pos = raw.index("€".encode())
    split_at = euro_pos + 1  # Split inside the 3-byte UTF-8 sequence.
    stream = ScriptedAsyncByteStream([raw[:split_at], raw[split_at:]])
    handlers[GENERATE] = lambda _: httpx2.Response(403, stream=stream)
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert stream.closed
    assert gemini_diagnostics(caplog) == [
        "Gemini diagnostic: category=upstream_http_error operation=generate_content "
        "http_status=403 upstream_error_status=PERMISSION_DENIED"
    ]
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "Denied", "café"):
        assert marker not in caplog.text + response.text + capture.out + capture.err


@pytest.mark.parametrize(
    "http_status,api_code,retryable",
    [
        (400, "AI_CONFIGURATION_ERROR", False),
        (429, "AI_PROVIDER_RATE_LIMITED", True),
    ],
)
def test_upstream_error_mid_stream_read_timeout_preserves_http_classification(
    deployment, monkeypatch, capsys, caplog, http_status, api_code, retryable
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    stream = ScriptedAsyncByteStream(
        [f'{{"error":{{"status":"INVALID_ARGUMENT","message":"{PRIVATE}'.encode()],
        fail_with=httpx2.ReadTimeout(f"midstream-read-timeout-marker {PRIVATE}"),
    )
    handlers[GENERATE] = lambda _: httpx2.Response(http_status, stream=stream)
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, api_code, retryable)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert stream.closed
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == api_code
    assert gemini_diagnostics(caplog) == [
        f"Gemini diagnostic: category=upstream_http_error operation=generate_content "
        f"http_status={http_status}"
    ]
    assert "upstream_error_status=" not in caplog.text
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "midstream-read-timeout-marker"):
        assert marker not in caplog.text + response.text + capture.out + capture.err + str(
            vars(row)
        )


def test_upstream_error_malformed_compression_preserves_http_classification(
    deployment, monkeypatch, capsys, caplog
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    stream = ScriptedAsyncByteStream([b"\x1f\x8b\x08\x00corrupt-" + PRIVATE.encode()])
    handlers[GENERATE] = lambda _: httpx2.Response(
        403,
        stream=stream,
        headers={"Content-Encoding": "gzip", "X-Leak": PRIVATE},
    )
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    assert stream.closed
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    assert gemini_diagnostics(caplog) == [
        "Gemini diagnostic: category=upstream_http_error operation=generate_content http_status=403"
    ]
    assert "upstream_error_status=" not in caplog.text
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY, "X-Leak"):
        assert marker not in caplog.text + response.text + capture.out + capture.err + str(
            vars(row)
        )


@pytest.mark.parametrize(
    "lifecycle,http_status",
    [
        ("consumed-without-content", 404),
        ("already-closed", 401),
    ],
)
def test_upstream_error_stream_lifecycle_failures_preserve_http_classification(
    deployment, monkeypatch, capsys, caplog, lifecycle, http_status
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)

    async def respond(_):
        stream = ScriptedAsyncByteStream(
            [
                json.dumps(
                    {
                        "error": {
                            "status": "NOT_FOUND" if http_status == 404 else "UNAUTHENTICATED",
                            "message": f"{PRIVATE} {SYNTHETIC_AQ_KEY}",
                        }
                    }
                ).encode()
            ]
        )
        resp = httpx2.Response(http_status, stream=stream)
        if lifecycle == "consumed-without-content":
            async for _ in resp.aiter_bytes():
                pass
            assert resp.is_stream_consumed
        else:
            await resp.aclose()
            assert resp.is_closed
        return resp

    handlers[GENERATE] = respond
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 503, "AI_CONFIGURATION_ERROR", False)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_CONFIGURATION_ERROR"
    assert gemini_diagnostics(caplog) == [
        f"Gemini diagnostic: category=upstream_http_error operation=generate_content "
        f"http_status={http_status}"
    ]
    assert "upstream_error_status=" not in caplog.text
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY):
        assert marker not in caplog.text + response.text + capture.out + capture.err + str(
            vars(row)
        )


@pytest.mark.parametrize("mode", ["valid-stream", "already-closed", "consumed-without-content"])
def test_upstream_error_without_attached_request_preserves_http_classification(
    caplog, capsys, mode
):
    stream = ScriptedAsyncByteStream(
        [
            json.dumps(
                {
                    "error": {
                        "status": "INVALID_ARGUMENT",
                        "message": f"{PRIVATE} {SYNTHETIC_AQ_KEY}",
                    }
                }
            ).encode()
        ]
    )
    resp = httpx2.Response(400, stream=stream)

    async def check():
        if mode == "already-closed":
            await resp.aclose()
        elif mode == "consumed-without-content":
            async for _ in resp.aiter_bytes():
                pass
        with pytest.raises(ProviderFailure) as exc_info:
            await validate_response_encoding(resp)
        assert exc_info.value.kind == "configuration"

    with caplog.at_level(logging.DEBUG):
        asyncio.run(check())
    capture = capsys.readouterr()
    assert stream.closed
    expected = "Gemini diagnostic: category=upstream_http_error operation=unknown http_status=400"
    if mode == "valid-stream":
        expected += " upstream_error_status=INVALID_ARGUMENT"
    assert gemini_diagnostics(caplog) == [expected]
    for marker in (PRIVATE, SYNTHETIC_AQ_KEY):
        assert marker not in caplog.text + capture.out + capture.err


@pytest.mark.parametrize(
    "violation",
    [
        "too-many-findings",
        "too-many-citations",
        "empty-rationale",
        "too-many-rationale",
        "too-many-limitations",
        "too-many-next-questions",
        "negative-citation-index",
        "oversized-citation-index",
    ],
)
def test_simplified_wire_schema_still_enforces_strict_application_bounds(
    gemini, wire, caplog, violation
):
    client, engine = gemini
    output = cited_output()
    finding = output["findings"][0]
    base_citation = dict(finding["citations"][0])
    base_rationale = dict(finding["rationale"][0])
    base_limitation = {
        "text": "Provider completeness is unverified.",
        "kind": "evidence_statement",
        "citation_indexes": [0],
        "result_source_keys": [],
    }
    match violation:
        case "too-many-findings":
            output["findings"] = [dict(finding) for _ in range(7)]
        case "too-many-citations":
            finding["citations"] = [dict(base_citation) for _ in range(9)]
        case "empty-rationale":
            finding["rationale"] = []
        case "too-many-rationale":
            finding["rationale"] = [dict(base_rationale) for _ in range(4)]
        case "too-many-limitations":
            finding["limitations"] = [dict(base_limitation) for _ in range(5)]
        case "too-many-next-questions":
            finding["next_questions"] = [f"Question {index}?" for index in range(4)]
        case "negative-citation-index":
            finding["rationale"][0]["citation_indexes"] = [-1]
        case "oversized-citation-index":
            finding["rationale"][0]["citation_indexes"] = [8]
        case _:
            raise AssertionError(f"Unsupported violation: {violation}")

    wire[1][GENERATE] = lambda _: httpx2.Response(200, json=gemini_body(output=output))
    workspace = prepare(client)
    with caplog.at_level(logging.DEBUG):
        response = generate(client, workspace)
    check_error(response, 502, "AI_OUTPUT_INVALID", True)
    assert [item.url.path for item in wire[0]] == [COUNT, GENERATE]
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_OUTPUT_INVALID"
    assert row.normalized_output is None
    assert graph_counts(engine, workspace) == [0] * 5
    assert FAKE_KEY not in response.text + caplog.text + str(vars(row))


def test_instructions_document_reference_format_and_citation_rules():
    for expected in (
        "evidence.source_outcomes[*].records[*]",
        "/payload/",
        "/timestamps/",
        "~0",
        "~1",
        "/payload/Amount~1currency",
        'role="supports"',
        "not_confirmed",
        "citation_indexes",
    ):
        assert expected in findings.INSTRUCTIONS


@pytest.mark.parametrize(
    "pointer,succeeds",
    [
        ("/payload/Amount/currency", False),
        ("/payload/Amount~1currency", True),
    ],
    ids=["unescaped-slash", "escaped-slash"],
)
def test_slash_field_pointer_escaping_and_publication(gemini, wire, pointer, succeeds):
    client, engine = gemini
    output = cited_output()
    output["findings"][0]["citations"][0]["pointer"] = pointer
    wire[1][GENERATE] = lambda _: httpx2.Response(200, json=gemini_body(output=output))
    workspace = prepare(client)
    response = generate(client, workspace)
    if succeeds:
        assert response.status_code == 201, response.text
        assert response.json()["findings"][0]["citations"][0]["value"] == "SGD 48.00"
        assert graph_counts(engine, workspace) == [1, 1, 1, 1, 0]
    else:
        check_error(response, 502, "AI_REFERENCE_INVALID", True)
        assert graph_counts(engine, workspace) == [0] * 5


@pytest.mark.parametrize(
    "scenario,expected_category",
    [
        ("invalid-locator", "invalid_locator"),
        ("missing-array-item", "missing_array_item"),
        ("missing-field", "missing_field"),
        ("duplicate-claim", "duplicate_claim"),
        ("unreturned-record", "unreturned_record"),
        ("duplicate-citation", "duplicate_citation"),
        ("citation-index-oob", "citation_index_oob"),
        ("unknown-source-key", "unknown_source_key"),
        ("confirmed-without-support", "confirmed_without_support"),
        ("not-confirmed-without-citation", "not_confirmed_without_citation"),
        ("uncited-hypothesis-invalid", "uncited_hypothesis_invalid"),
    ],
)
def test_reference_validation_diagnostics_classify_every_rule_without_leaking(
    deployment, monkeypatch, capsys, caplog, scenario, expected_category
):
    engine, config = deployment
    received, handlers = install_wire(monkeypatch, expected_key=SYNTHETIC_AQ_KEY)
    output = cited_output()
    finding = output["findings"][0]
    finding["claim"] = f"Claim {PRIVATE}"
    finding["citations"][0]["explanation"] = f"Explanation {PRIVATE}"
    match scenario:
        case "invalid-locator":
            finding["citations"][0]["pointer"] = f"/other/{PRIVATE}"
        case "missing-array-item":
            finding["citations"][0]["pointer"] = "/timestamps/9"
        case "missing-field":
            finding["citations"][0]["pointer"] = f"/payload/{PRIVATE}"
        case "duplicate-claim":
            second = json.loads(json.dumps(finding))
            second["claim"] = f"  claim   {PRIVATE.lower()} "
            output["findings"].append(second)
        case "unreturned-record":
            finding["citations"][0]["evidence_record_id"] = "SYN-PO-ATT-002-A"
        case "duplicate-citation":
            finding["citations"].append(dict(finding["citations"][0]))
        case "citation-index-oob":
            finding["rationale"][0]["citation_indexes"] = [1]
        case "unknown-source-key":
            finding["rationale"][0]["result_source_keys"] = ["stripe"]
            # Override the bundle check by passing an unknown key only if schema allows;
            # schema restricts Literal QuerySource, so test validate_references directly below.
            pass
        case "confirmed-without-support":
            finding["proposed_status"] = "confirmed"
            finding["citations"][0]["role"] = "context"
        case "not-confirmed-without-citation":
            finding["proposed_status"] = "not_confirmed"
            finding["citations"] = []
            finding["rationale"][0]["citation_indexes"] = []
            finding["rationale"][0]["result_source_keys"] = ["stripe"]
        case "uncited-hypothesis-invalid":
            finding["kind"] = "hypothesis"
            finding["proposed_status"] = "inconclusive"
            finding["citations"] = []
            finding["rationale"][0]["citation_indexes"] = []
            finding["rationale"][0]["result_source_keys"] = ["stripe"]
        case _:
            raise AssertionError(f"Unsupported scenario: {scenario}")

    if scenario == "unknown-source-key":
        # Unknown retrieval outcome cannot be produced via QuerySource Literal on HTTP output,
        # so verify the exact validate_references branch directly.
        from app.findings_validation import validate_references

        bundle = {
            "evidence": {
                "source_outcomes": [
                    {
                        "source_key": "internal_payments",
                        "records": [
                            {
                                "evidence_record_id": "SYN-PO-ATT-001",
                                "payload": {"Internal status": "Outcome unknown after timeout"},
                            }
                        ],
                    }
                ]
            }
        }
        parsed = FindingGenerationOutput.model_validate(output)
        with pytest.raises(ValueError, match="Unknown retrieval outcome") as exc_info:
            validate_references(parsed, bundle)
        assert findings.REFERENCE_DIAGNOSTIC_CATEGORIES[str(exc_info.value)] == expected_category
        return

    handlers[GENERATE] = lambda _: httpx2.Response(200, json=gemini_body(output=output))
    aq_config = config.model_copy(update={"gemini_api_key": SecretStr(SYNTHETIC_AQ_KEY)})
    with worker(aq_config) as client:
        bootstrap(client)
        workspace = prepare(client)
        with caplog.at_level(logging.DEBUG):
            response = generate(client, workspace)
        check_error(response, 502, "AI_REFERENCE_INVALID", True)
        assert [item.url.path for item in received] == [COUNT, GENERATE]

    capture = capsys.readouterr()
    (row,) = attempts(engine, workspace)
    assert row.status == "failed" and row.failure_code == "AI_REFERENCE_INVALID"
    assert row.normalized_output is None
    assert graph_counts(engine, workspace) == [0] * 5
    diagnostic_lines = [
        record.getMessage() for record in caplog.records if record.name == "app.findings"
    ]
    assert diagnostic_lines == [
        f"Findings reference validation rejected output: category={expected_category} "
        "provider=gemini"
    ]
    for marker in (
        PRIVATE,
        SYNTHETIC_AQ_KEY,
        "SYN-PO-ATT-001",
        "SYN-PO-ATT-002-A",
        "/other/",
        "/timestamps/9",
        "Claim ",
        "Invalid evidence locator",
        "Missing evidence field",
    ):
        assert marker not in caplog.text
        assert marker not in response.text
        assert marker not in capture.out + capture.err
