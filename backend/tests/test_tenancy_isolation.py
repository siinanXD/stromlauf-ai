"""Isolation zwischen Workspaces gegen echte Postgres (CI-Service). Lokal: STROMLAUF_DB_TESTS=1 setzen.

Prueft die zwei Sicherungen aus app/tenancy.py an der laufenden App: Workspace A sieht keine
Quellen, Dokumente, Kennzeichen, Maschinen oder Chats von Workspace B, weder per Liste noch per id.
"""

import os
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)")

SECRET = "isolation-test-secret-0123456789"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["JWT_SECRET"] = SECRET
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def workspaces(client):
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import User, Workspace, WorkspaceMember

    tokens = {}
    with session_scope() as session:
        for key in ("a", "b"):
            workspace = Workspace(id=f"ws-{key}-test", name=f"Werk {key.upper()}")
            user = User(id=f"user-{key}-test", email=f"{key}@isolation.test")
            session.merge(workspace)
            session.merge(user)
            session.merge(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            tokens[key], _ = issue_token(user_id=user.id, email=user.email, workspace_id=workspace.id, role="admin", secret=SECRET, hours=1)
    return tokens


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_ohne_token_401(client, workspaces):
    assert client.get("/api/sources").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_quellen_und_dokumente_sind_getrennt(client, workspaces):
    a, b = workspaces["a"], workspaces["b"]
    created = client.post("/api/sources", json={"name": "Anlage A", "description": ""}, headers=_auth(a))
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    assert [s["id"] for s in client.get("/api/sources", headers=_auth(a)).json()] == [source_id]
    assert source_id not in [s["id"] for s in client.get("/api/sources", headers=_auth(b)).json()]
    assert client.get(f"/api/sources/{source_id}/documents", headers=_auth(b)).status_code == 404
    assert client.delete(f"/api/sources/{source_id}", headers=_auth(b)).status_code == 404
    assert client.get(f"/api/sources/{source_id}/documents", headers=_auth(a)).status_code == 200


def test_kennzeichen_index_ist_getrennt(client, workspaces):
    from app.db import session_scope
    from app.models import Document, KnowledgeSource, TagOccurrence
    from app.tenancy import reset_workspace, set_workspace

    a, b = workspaces["a"], workspaces["b"]
    token = set_workspace("ws-a-test")
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Index A")
            session.add(source)
            session.flush()
            document = Document(source_id=source.id, filename="plan.pdf", storage_path="/nirgends/plan.pdf", doc_type="schematic", status="ready")
            session.add(document)
            session.flush()
            session.add(TagOccurrence(document_id=document.id, source_id=source.id, tag="-K77", tag_type="device", page=3, context="Schuetz"))
    finally:
        reset_workspace(token)

    hits_a = client.get("/api/tags/search", params={"q": "-K77"}, headers=_auth(a)).json()
    hits_b = client.get("/api/tags/search", params={"q": "-K77"}, headers=_auth(b)).json()
    assert [h["tag"] for h in hits_a] == ["-K77"]
    assert hits_b == []
    assert client.get("/api/facts", params={"tag": "-K77"}, headers=_auth(a)).status_code == 200
    assert client.get("/api/facts", params={"tag": "-K77"}, headers=_auth(b)).status_code == 404


def test_maschinen_und_chats_sind_getrennt(client, workspaces):
    a, b = workspaces["a"], workspaces["b"]
    hall = client.post("/api/halls", json={"name": "Halle A", "description": ""}, headers=_auth(a)).json()
    machine = client.post(f"/api/halls/{hall['id']}/machines", json={"name": "Presse", "machine_type": "main", "description": ""}, headers=_auth(a)).json()
    assert client.get(f"/api/machines/{machine['id']}", headers=_auth(a)).status_code == 200
    assert client.get(f"/api/machines/{machine['id']}", headers=_auth(b)).status_code == 404
    assert machine["id"] not in [m["id"] for m in client.get("/api/machines", headers=_auth(b)).json()]
    assert client.patch(f"/api/machines/{machine['id']}", json={"name": "x"}, headers=_auth(b)).status_code == 404

    from app.db import session_scope
    from app.models import Conversation
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace("ws-a-test")
    try:
        with session_scope() as session:
            conversation = Conversation(title="Nur A", source_ids=[], updated_at=datetime.now(timezone.utc))
            session.add(conversation)
            session.flush()
            conversation_id = conversation.id
    finally:
        reset_workspace(token)
    assert conversation_id in [c["id"] for c in client.get("/api/conversations", headers=_auth(a)).json()]
    assert conversation_id not in [c["id"] for c in client.get("/api/conversations", headers=_auth(b)).json()]
    assert client.get(f"/api/conversations/{conversation_id}/messages", headers=_auth(b)).status_code == 404
    assert client.delete(f"/api/conversations/{conversation_id}", headers=_auth(b)).status_code == 404


def test_me_und_magic_link_exchange(client, workspaces):
    me = client.get("/api/auth/me", headers=_auth(workspaces["a"])).json()
    assert me["workspace"]["id"] == "ws-a-test" and me["email"] == "a@isolation.test"
    assert client.get("/api/auth/mode").json()["mode"] == "jwt"

    os.environ["AUTH_DEV_LINK"] = "true"
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        requested = client.post("/api/auth/magic-link", json={"email": "neu@isolation.test"})
        assert requested.status_code == 202, requested.text
        link = requested.json()["dev_link"]
        raw = link.split("token=", 1)[1]
        exchanged = client.post("/api/auth/exchange", json={"token": raw})
        assert exchanged.status_code == 200, exchanged.text
        body = exchanged.json()
        assert body["email"] == "neu@isolation.test" and body["workspace"]["role"] == "admin"
        # neuer Nutzer = eigener, leerer Workspace
        assert client.get("/api/sources", headers=_auth(body["token"])).json() == []
        # Token nur einmal einloesbar
        assert client.post("/api/auth/exchange", json={"token": raw}).status_code == 401
    finally:
        os.environ.pop("AUTH_DEV_LINK", None)
        get_settings.cache_clear()
