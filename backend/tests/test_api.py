import logging
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, SecretStr

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    # Unit tests never connect to this address. Readiness outcomes are patched explicitly.
    app = create_app(Settings(database_url="postgresql+psycopg://localhost/unused"))
    monkeypatch.setattr("app.main.initialize_catalog", lambda *args: None)

    class TestPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        count: int

    @app.post("/test/payload")
    def echo(payload: TestPayload):
        return payload

    with TestClient(app) as test_client:
        yield test_client


def test_health_contract_has_no_identity_or_cache(client, monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda *args: None)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected", "schema": "current"}
    UUID(response.headers["X-Request-ID"])
    assert response.headers["Cache-Control"] == "no-store"
    assert "set-cookie" not in response.headers


@pytest.fixture
def startup_diagnostics(monkeypatch, caplog):
    engine = Mock()
    catalog = Mock(return_value=None)
    monkeypatch.setattr("app.main.build_engine", Mock(return_value=engine))
    monkeypatch.setattr("app.main.initialize_catalog", catalog)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        yield engine, catalog


@pytest.mark.parametrize(
    "overrides,provider,ready",
    [
        ({"ai_findings_provider": "gemini"}, "gemini", True),
        ({"ai_findings_provider": "gemini"}, "gemini", False),
        ({"ai_findings_provider": "openai"}, "openai", True),
        ({"ai_findings_provider": "openai"}, "openai", False),
        ({}, "mock", True),
        ({"ai_findings_provider": "gemini", "ai_findings_enabled": False}, "disabled", False),
        (
            {"ai_findings_provider": "gemini", "ai_findings_gemini_model": "private-model-marker"},
            "unsupported",
            False,
        ),
        ({"ai_findings_provider": "private-provider-marker"}, "unsupported", False),
    ],
    ids=[
        "gemini-ready",
        "gemini-unavailable",
        "openai-ready",
        "openai-unavailable",
        "mock-ready",
        "disabled",
        "unsupported-model",
        "unsupported-provider",
    ],
)
def test_findings_adapter_startup_diagnostic(
    overrides, provider, ready, startup_diagnostics, monkeypatch, caplog
):
    engine, catalog = startup_diagnostics
    test_key = SecretStr("synthetic-startup-key-marker")
    settings = Settings(
        database_url="postgresql+psycopg://localhost/unused",
        ai_findings_enabled=True,
        gemini_api_key=test_key,
        openai_api_key=test_key,
    ).model_copy(update=overrides)
    adapter = Mock(close=AsyncMock())
    gemini = AsyncMock(return_value=adapter if ready else None)
    openai = Mock(return_value=adapter if ready else None)
    monkeypatch.setattr("app.main.build_gemini_provider", gemini)
    monkeypatch.setattr("app.main.build_openai_provider", openai)

    app = create_app(settings)
    with TestClient(app):
        assert (app.state.findings_provider is not None) == ready

    expected_gemini = [call(test_key)] if provider == "gemini" else []
    assert gemini.call_args_list == gemini.await_args_list == expected_gemini
    assert openai.call_args_list == ([call(test_key)] if provider == "openai" else [])
    assert adapter.close.await_count == int(ready and provider in {"gemini", "openai"})
    catalog.assert_called_once()
    engine.dispose.assert_called_once_with()
    records = [record for record in caplog.records if record.name == "uvicorn.error.opspilot"]
    assert len(records) == 1
    assert records[0].getMessage() == (
        f"ai_findings_adapter_startup provider={provider} ready={str(ready).lower()}"
    )
    assert records[0].exc_info is None


def test_findings_adapter_startup_error_propagates_without_logging_exception(
    startup_diagnostics, monkeypatch, caplog
):
    engine, catalog = startup_diagnostics
    failure = RuntimeError("synthetic-private-startup-error")
    monkeypatch.setattr("app.main.build_gemini_provider", AsyncMock(side_effect=failure))
    settings = Settings(
        database_url="postgresql+psycopg://localhost/unused",
        ai_findings_enabled=True,
        ai_findings_provider="gemini",
    )

    with pytest.raises(RuntimeError) as error, TestClient(create_app(settings)):
        pass

    assert error.value is failure
    records = [record for record in caplog.records if record.name == "uvicorn.error.opspilot"]
    assert len(records) == 1
    assert records[0].getMessage() == "ai_findings_adapter_startup provider=gemini ready=false"
    assert records[0].exc_info is None
    catalog.assert_not_called()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("code", ["DATABASE_UNAVAILABLE", "SCHEMA_NOT_READY"])
def test_unready_health_is_visible_retryable_and_correlated(client, monkeypatch, code):
    monkeypatch.setattr("app.main.check_database", lambda *args: code)
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == code
    assert error["retryable"] is True
    assert error["details"] == {}
    assert error["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize("origin", [None, "null", "http://localhost:3000", "https://other.test"])
def test_post_rejects_missing_or_foreign_origin(client, origin):
    headers = {"X-OpsPilot-Request": "1"}
    if origin is not None:
        headers["Origin"] = origin
    response = client.post("/api/v1/health", json={}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REQUEST_ORIGIN_FORBIDDEN"


def test_post_requires_custom_header(client):
    response = client.post("/api/v1/health", json={}, headers={"Origin": "https://localhost:3000"})
    assert response.status_code == 403


def test_post_rejects_wrong_media_and_oversized_body(client):
    headers = {"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"}
    response = client.post("/api/v1/health", content="{}", headers=headers)
    assert response.status_code == 415
    headers["Content-Type"] = "application/json"
    response = client.post("/api/v1/health", content=b" " * 4097, headers=headers)
    assert response.status_code == 413


def test_body_limit_covers_stream_without_content_length(client):
    headers = {
        "Origin": "https://localhost:3000",
        "X-OpsPilot-Request": "1",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/health", content=iter([b" " * 2048, b" " * 2049]), headers=headers
    )
    assert response.status_code == 413


def test_workspace_route_requires_authentication_before_lookup(client):
    response = client.get("/api/v1/investigations/unknown/workspace")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


def test_browser_harness_routes_are_not_mounted_in_application(client):
    assert client.get("/api/v1/_session-tests").status_code == 404
    assert client.get("/api/v1/_session-tests/current").status_code == 404
    response = client.post(
        "/api/v1/_session-tests/control",
        json={"operation": "advance"},
        headers={"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"},
    )
    assert response.status_code == 404


def test_valid_post_body_reaches_validation_without_echoing_invalid_input(client):
    headers = {"Origin": "https://localhost:3000", "X-OpsPilot-Request": "1"}
    response = client.post("/test/payload", json={"count": 1}, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"count": 1}
    response = client.post("/test/payload", json={"count": "sensitive input"}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sensitive" not in response.text


def test_unexpected_failure_does_not_expose_exception_input(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("sensitive database connection string")

    monkeypatch.setattr("app.main.check_database", fail)
    response = client.get("/api/v1/health")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "sensitive" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "https://localhost:3000/",
        "https://user:password@localhost:3000",
        "https://localhost/path",
    ],
)
def test_configuration_requires_exact_https_origin(origin):
    with pytest.raises(ValueError):
        Settings(database_url="postgresql+psycopg://localhost/unused", public_origin=origin)
