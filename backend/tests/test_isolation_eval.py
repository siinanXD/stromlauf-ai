"""Isolations-Eval (Issue #29, MB-2): fuenf Retrieval-Fragen duerfen keine Inhalte aus einem fremden Workspace liefern.

Workspace B bekommt Kennzeichen, Chunks und eine Maschine; Workspace A stellt dieselben fuenf Fragen ueber die
Retrieval-Endpunkte (Kennzeichen, Befundkarte, Stichwort, Maschinen-Tag, Signalweg) und muss leer ausgehen.
Laeuft gegen Postgres (CI); lokal STROMLAUF_DB_TESTS=1.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)")

SECRET = "isolation-eval-secret-0123456789abc"
TAGS = ["-K77", "-M42", "-F9", "-X7:3", "-Q5"]


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
def world(client):
    """Workspace B mit Daten, Workspace A leer; Tokens fuer beide."""
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import (
        Document,
        KnowledgeSource,
        TagOccurrence,
        User,
        Workspace,
        WorkspaceMember,
    )
    from app.tenancy import reset_workspace, set_workspace

    tokens = {}
    with session_scope() as session:
        for key in ("a", "b"):
            session.merge(Workspace(id=f"ws-eval-{key}", name=f"Eval {key.upper()}"))
            session.merge(User(id=f"user-eval-{key}", email=f"{key}@isolation-eval.de"))
            session.merge(WorkspaceMember(workspace_id=f"ws-eval-{key}", user_id=f"user-eval-{key}", role="admin"))
            tokens[key], _ = issue_token(user_id=f"user-eval-{key}", email=f"{key}@isolation-eval.de", workspace_id=f"ws-eval-{key}", role="admin", secret=SECRET, hours=1)

    token = set_workspace("ws-eval-b")
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Geheime Anlage B")
            session.add(source)
            session.flush()
            document = Document(source_id=source.id, filename="geheim.pdf", storage_path="/nirgends/geheim.pdf", doc_type="schematic", status="ready")
            bom = Document(source_id=source.id, filename="geheim_stueckliste.xlsx", storage_path="/nirgends/geheim.xlsx", doc_type="bom", status="ready")
            session.add_all([document, bom])
            session.flush()
            for i, tag in enumerate(TAGS, 1):
                kind = "terminal" if ":" in tag else "device"
                session.add(TagOccurrence(document_id=document.id, source_id=source.id, tag=tag, tag_type=kind, page=i, context=f"{tag} Geheimnis {i} /{i}.2"))
                session.add(TagOccurrence(document_id=bom.id, source_id=source.id, tag=tag, tag_type=kind, page=None, context=f"| {tag} | Geheimteil {i} | ART-{i} | +ST1 |"))
            source_id = source.id
    finally:
        reset_workspace(token)
    hall = client.post("/api/halls", json={"name": "Halle B", "description": ""}, headers={"Authorization": f"Bearer {tokens['b']}"}).json()
    machine = client.post(f"/api/halls/{hall['id']}/machines", json={"name": "Geheimpresse", "machine_type": "main", "description": "", "source_id": source_id}, headers={"Authorization": f"Bearer {tokens['b']}"}).json()
    return {"tokens": tokens, "source_id": source_id, "machine_id": machine["id"]}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_fuenf_fragen_liefern_nichts_aus_dem_fremden_workspace(client, world):
    a, b = world["tokens"]["a"], world["tokens"]["b"]
    source_id, machine_id = world["source_id"], world["machine_id"]

    # 1. Kennzeichen-Suche: B sieht seine Treffer, A nichts
    assert [h["tag"] for h in client.get("/api/tags/search", params={"q": "-K77"}, headers=_auth(b)).json()] == ["-K77"]
    assert client.get("/api/tags/search", params={"q": "-K77"}, headers=_auth(a)).json() == []
    # 2. Befundkarte
    assert client.get("/api/facts", params={"tag": "-M42", "source_ids": [source_id]}, headers=_auth(b)).status_code == 200
    assert client.get("/api/facts", params={"tag": "-M42", "source_ids": [source_id]}, headers=_auth(a)).status_code == 404
    # 3. Kennzeichen- und Stichwortsuche mit der fremden Quelle als Scope: keine Fundstellen (B sieht den Index-Treffer)
    mine = client.get("/api/search", params={"mode": "tag", "q": "-F9", "source_id": source_id}, headers=_auth(b))
    assert mine.status_code == 200 and mine.json().get("refs"), mine.text
    for mode in ("tag", "keyword"):  # semantic braucht das Embedding-Modell, nicht Teil dieses Tests
        foreign = client.get("/api/search", params={"mode": mode, "q": "-F9 Geheimteil", "source_id": source_id}, headers=_auth(a))
        assert foreign.status_code in (404, 422) or not foreign.json().get("refs"), foreign.text
    # 4. Maschinen-Tag-Lookup ueber die fremde Maschine
    assert client.get(f"/api/machines/{machine_id}/tags/-Q5", headers=_auth(b)).json()["hits"]
    assert client.get(f"/api/machines/{machine_id}/tags/-Q5", headers=_auth(a)).status_code == 404
    # 5. Signalweg der fremden Quelle
    assert client.get("/api/signal-path", params={"tag": "-X7:3", "source_id": source_id}, headers=_auth(a)).status_code == 404
    # und die Quelle selbst bleibt unsichtbar
    assert source_id not in [s["id"] for s in client.get("/api/sources", headers=_auth(a)).json()]
