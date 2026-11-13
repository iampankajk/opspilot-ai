from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

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
