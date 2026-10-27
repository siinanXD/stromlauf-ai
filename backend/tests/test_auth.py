"""Zugriff und Mandant: JWT, API-Key, offener Modus - ohne Datenbank."""

from datetime import datetime, timedelta, timezone

import jwt

from app import auth

SECRET = "test-secret-0123456789"


def _headers(**values):
    return {k.lower().replace("_", "-"): v for k, v in values.items()}


def test_jwt_roundtrip():
    token, expires = auth.issue_token(user_id="u1", email="a@b.de", workspace_id="ws1", role="admin", secret=SECRET, hours=1)
    principal = auth.principal_from_token(token, SECRET)
    assert principal is not None
    assert (principal.user_id, principal.email, principal.workspace_id, principal.role, principal.via) == (
        "u1", "a@b.de", "ws1", "admin", "jwt",
    )
    assert expires > datetime.now(timezone.utc)


def test_abgelaufenes_oder_fremdes_jwt_wird_abgelehnt():
    expired = jwt.encode({"sub": "u", "ws": "w", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET, algorithm="HS256")
    assert auth.principal_from_token(expired, SECRET) is None
    other = jwt.encode({"sub": "u", "ws": "w", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "anderes-secret", algorithm="HS256")
    assert auth.principal_from_token(other, SECRET) is None
    assert auth.principal_from_token("kein.jwt", SECRET) is None


def test_credentials_in_prioritaet():
    found = auth.presented_credentials(_headers(authorization="Bearer AAA", x_api_key="BBB"), {"api_key": "CCC", "token": "DDD"}, "GET")
    assert found == ["AAA", "BBB", "CCC", "DDD"]
    assert auth.presented_credentials(_headers(), {"token": "DDD"}, "POST") == []


def test_api_key_ist_dienstzugriff_im_default_workspace():
    principal = auth.resolve_principal(["geheim"], api_key="geheim", jwt_secret=SECRET)
    assert principal is not None and principal.workspace_id == "default" and principal.via == "api_key"
    assert auth.resolve_principal(["falsch"], api_key="geheim", jwt_secret=None) is None


def test_jwt_geht_auch_als_api_key_header():
    token, _ = auth.issue_token(user_id="u1", email="a@b.de", workspace_id="ws9", role="member", secret=SECRET, hours=1)
    principal = auth.resolve_principal([token], api_key="geheim", jwt_secret=SECRET)
    assert principal is not None and principal.workspace_id == "ws9" and principal.role == "member"


def test_offen_nur_ohne_jeden_schluessel():
    assert auth.resolve_principal([], api_key=None, jwt_secret=None).via == "open"
    assert auth.resolve_principal([], api_key=None, jwt_secret=SECRET) is None
    assert auth.resolve_principal([], api_key="geheim", jwt_secret=None) is None


def test_offene_pfade():
    assert auth.is_open("/api/health", "GET")
    assert auth.is_open("/api/auth/magic-link", "POST")
    assert auth.is_open("/api/sources", "OPTIONS")
    assert not auth.is_open("/api/sources", "GET")
    assert auth.is_open("/api/auth/mode", "GET")
    assert not auth.is_open("/api/auth/me", "GET")


def test_agent_konto_darf_nur_lesen():
    agent = auth.Principal(workspace_id="ws1", role=auth.AGENT_ROLE, via="jwt")
    assert agent.is_agent and not agent.is_admin
    for method in ("GET", "HEAD", "OPTIONS"):
        assert auth.agent_may(agent, method)
    for method in ("POST", "PUT", "PATCH", "DELETE", "post"):
        assert not auth.agent_may(agent, method)
    assert auth.agent_may(auth.Principal(workspace_id="ws1", role="admin"), "DELETE")
    assert auth.agent_may(auth.Principal(workspace_id="ws1", role="member"), "POST")


def test_agent_konto_bekommt_403_ueber_die_middleware(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.config import get_settings

    app = FastAPI()
    app.middleware("http")(auth.auth_middleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.post("/api/ping")
    def act():
        return {"ok": True}

    monkeypatch.setattr(get_settings(), "jwt_secret", SECRET)
    token, _ = auth.issue_token(user_id="a", email="agent@x.de", workspace_id="ws1", role=auth.AGENT_ROLE, secret=SECRET, hours=1)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/ping", headers=headers).status_code == 200
    assert client.post("/api/ping", headers=headers).status_code == 403


def test_agent_email_wird_ohne_gross_klein_erkannt():
    from app.api.auth import is_agent_email

    assert is_agent_email("Agent@X.de", "agent@x.de")
    assert not is_agent_email("andere@x.de", "agent@x.de")
    assert not is_agent_email("agent@x.de", None)
