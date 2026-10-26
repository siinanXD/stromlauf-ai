"""Demo-Modus: Schreibsperre (403), Rate-Limit (429), Chat bleibt offen - ohne Datenbank."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import demo


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(demo.demo_middleware)

    @app.get("/api/sources")
    def sources():
        return []

    @app.post("/api/chat")
    def chat():
        return {"ok": True}

    @app.post("/api/sources/x/documents")
    def upload():
        return {"ok": True}

    @app.delete("/api/documents/{document_id}")
    def delete(document_id: str):
        return {"ok": True}

    @app.patch("/api/machines/{machine_id}")
    def patch(machine_id: str):
        return {"ok": True}

    @app.put("/api/machines/{machine_id}/specs")
    def put(machine_id: str):
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def settings(monkeypatch):
    values = SimpleNamespace(demo_mode=True, demo_rate_limit=100, demo_chat_rate_limit=3, demo_trust_proxy=False)
    monkeypatch.setattr("app.config.get_settings", lambda: values)
    monkeypatch.setattr(demo, "limiter", demo.RateLimiter())
    return values


def test_schreibzugriffe_liefern_403(settings):
    client = TestClient(_app())
    assert client.post("/api/sources/x/documents", files={"file": ("a.pdf", b"x")}).status_code == 403
    assert client.delete("/api/documents/1").status_code == 403
    assert client.patch("/api/machines/1").status_code == 403
    assert client.put("/api/machines/1/specs").status_code == 403
    assert demo.write_blocked("POST", "/api/runs")
    assert client.post("/api/sources/x/documents").json()["code"] == "demo_readonly"


def test_lesen_und_chat_funktionieren(settings):
    client = TestClient(_app())
    assert client.get("/api/sources").status_code == 200
    assert client.post("/api/chat").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_ohne_demo_modus_bleibt_alles_offen(settings):
    settings.demo_mode = False
    client = TestClient(_app())
    assert client.delete("/api/documents/1").status_code == 200


def test_chat_rate_limit_greift_mit_429(settings):
    client = TestClient(_app())
    assert [client.post("/api/chat").status_code for _ in range(3)] == [200, 200, 200]
    response = client.post("/api/chat")
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert client.get("/api/sources").status_code == 200  # Lesen zaehlt nur gegen das Gesamtlimit


def test_gesamtlimit_je_ip(settings):
    settings.demo_rate_limit = 2
    client = TestClient(_app())
    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/sources").status_code == 429
    assert client.get("/api/health").status_code == 200  # Health bleibt frei


def test_limit_gilt_je_ip_und_proxy_header(settings):
    settings.demo_rate_limit = 1
    settings.demo_trust_proxy = True
    client = TestClient(_app())
    assert client.get("/api/sources", headers={"x-forwarded-for": "9.9.9.9, 1.1.1.1"}).status_code == 200
    assert client.get("/api/sources", headers={"x-forwarded-for": "9.9.9.9, 1.1.1.1"}).status_code == 429
    assert client.get("/api/sources", headers={"x-forwarded-for": "9.9.9.9, 2.2.2.2"}).status_code == 200


def test_fenster_laeuft_ab():
    now = [0.0]
    limiter = demo.RateLimiter(window_s=60, clock=lambda: now[0])
    assert limiter.hit("ip", 1) == 0
    assert limiter.hit("ip", 1) > 0
    now[0] = 61
    assert limiter.hit("ip", 1) == 0


def test_demo_modus_ist_standardmaessig_aus():
    from app.config import Settings

    assert Settings(_env_file=None).demo_mode is False
