"""API-Key-Schutz: ohne Schluessel offen, mit Schluessel nur Header, Bearer oder ?api_key."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import api_key_middleware, is_allowed, presented_key


def test_open_when_no_key_configured():
    assert is_allowed("/api/sources", "GET", None, None)
    assert is_allowed("/api/sources", "GET", "", None)


def test_health_and_preflight_stay_open():
    assert is_allowed("/api/health", "GET", "geheim", None)
    assert is_allowed("/api/sources", "OPTIONS", "geheim", None)
    assert is_allowed("/docs", "GET", "geheim", None)


def test_key_required_and_compared_exactly():
    assert not is_allowed("/api/sources", "GET", "geheim", None)
    assert not is_allowed("/api/sources", "GET", "geheim", "Geheim")
    assert is_allowed("/api/sources", "GET", "geheim", "geheim")


def test_presented_key_sources():
    assert presented_key({"x-api-key": "a"}, {}) == "a"
    assert presented_key({"authorization": "Bearer b"}, {}) == "b"
    assert presented_key({"authorization": "Basic b"}, {}) is None
    assert presented_key({}, {"api_key": "c"}) == "c"
    assert presented_key({}, {}) is None


def _app(monkeypatch, key: str | None) -> TestClient:
    from app import config

    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(api_key=key))
    app = FastAPI()
    app.middleware("http")(api_key_middleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return TestClient(app)


def test_middleware_rejects_without_key(monkeypatch):
    client = _app(monkeypatch, "geheim")
    assert client.get("/api/ping").status_code == 401
    assert "X-API-Key" in client.get("/api/ping").json()["detail"]
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ping", headers={"X-API-Key": "geheim"}).status_code == 200
    assert client.get("/api/ping?api_key=geheim").status_code == 200
    assert client.get("/api/ping", headers={"Authorization": "Bearer geheim"}).status_code == 200


def test_middleware_open_without_configured_key(monkeypatch):
    client = _app(monkeypatch, None)
    assert client.get("/api/ping").status_code == 200
