"""Wissen-API gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): /api/machines/{id}/notes."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "wissen-test-secret-0123456789abcdefgh"
WS = "ws-wissen-test"
WS_FREMD = "ws-wissen-fremd"


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


def _wipe(workspace_id: str) -> None:
    """Quellen (Cascade: Dokumente, Laeufe) und Maschinen des Workspace loeschen."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import KnowledgeSource, Machine
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(workspace_id)
    try:
        with session_scope() as session:
            for machine in session.scalars(select(Machine)).all():
                session.delete(machine)
            for source in session.scalars(select(KnowledgeSource)).all():
                session.delete(source)
    finally:
        reset_workspace(token)


def _login(workspace_id: str) -> dict:
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import User, Workspace, WorkspaceMember

    with session_scope() as session:
        session.merge(Workspace(id=workspace_id, name=workspace_id))
        session.merge(User(id=f"user-{workspace_id}", email=f"{workspace_id}@wissen-test.de"))
        session.merge(
            WorkspaceMember(workspace_id=workspace_id, user_id=f"user-{workspace_id}", role="admin")
        )
    access, _ = issue_token(
        user_id=f"user-{workspace_id}",
        email=f"{workspace_id}@wissen-test.de",
        workspace_id=workspace_id,
        role="admin",
        secret=SECRET,
        hours=1,
    )
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture(scope="module")
def headers(client):
    _wipe(WS)
    yield _login(WS)
    _wipe(WS)


@pytest.fixture(scope="module")
def fremde_headers(client):
    yield _login(WS_FREMD)
    _wipe(WS_FREMD)


def _maschine(headers) -> tuple[str, str]:
    """Quelle, Dokument, Halle und Maschine im Test-Workspace anlegen; (machine_id, document_id)."""
    from app.db import session_scope
    from app.models import DocStatus, Document, Hall, KnowledgeSource, Machine
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            quelle = KnowledgeSource(name="Quelle")
            session.add(quelle)
            session.flush()
            dokument = Document(
                source_id=quelle.id,
                filename="01_Plan.pdf",
                storage_path="x",
                status=DocStatus.READY,
            )
            halle = Hall(name="Halle")
            session.add_all([dokument, halle])
            session.flush()
            maschine = Machine(hall_id=halle.id, name="FB-01", source_id=quelle.id)
            session.add(maschine)
            session.flush()
            return maschine.id, dokument.id
    finally:
        reset_workspace(token)


def test_tabelle_leer_und_post_patch_delete(client, headers):
    machine_id, document_id = _maschine(headers)
    assert client.get(f"/api/machines/{machine_id}/notes", headers=headers).json() == []
    body = {"text": "Der Antrieb ist -M1.", "belege": [{"document_id": document_id, "page": 3}]}
    created = client.post(f"/api/machines/{machine_id}/notes", json=body, headers=headers)
    assert created.status_code == 201
    note = created.json()
    assert note["quelle"] == "mensch" and note["gesperrt"] is True
    assert note["belege"][0]["filename"] == "01_Plan.pdf"
    patched = client.patch(
        f"/api/machines/{machine_id}/notes/{note['id']}",
        json={"text": "Der Antrieb ist -M1 (4 kW)."},
        headers=headers,
    )
    assert patched.status_code == 200 and patched.json()["text"] == "Der Antrieb ist -M1 (4 kW)."
    from app.config import get_settings
    from app.wissen.obsidian import dateiname

    ordner = get_settings().data_dir / "wissen"
    datei = ordner / f"{dateiname('FB-01', machine_id)}.md"
    inhalt = datei.read_text(encoding="utf-8")
    assert "Der Antrieb ist -M1 (4 kW)." in inhalt and "machine_id:" in inhalt
    assert client.delete(f"/api/machines/{machine_id}/notes/{note['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/machines/{machine_id}/notes", headers=headers).json() == []
    assert "Der Antrieb" not in datei.read_text(encoding="utf-8")
    assert list(ordner.glob("*.tmp")) == []


def test_post_dublette_bleibt_einmal(client, headers):
    machine_id, document_id = _maschine(headers)
    body = {"text": "-F2 schützt -M1.", "belege": [{"document_id": document_id, "page": None}]}
    first = client.post(f"/api/machines/{machine_id}/notes", json=body, headers=headers)
    second = client.post(
        f"/api/machines/{machine_id}/notes", json={**body, "text": "  -f2 schützt -M1 "}, headers=headers
    )
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(client.get(f"/api/machines/{machine_id}/notes", headers=headers).json()) == 1


def test_post_ohne_beleg_oder_fremdes_dokument_400(client, headers):
    machine_id, _ = _maschine(headers)
    r = client.post(f"/api/machines/{machine_id}/notes", json={"text": "X.", "belege": []}, headers=headers)
    assert r.status_code == 422
    r = client.post(
        f"/api/machines/{machine_id}/notes",
        json={"text": "X.", "belege": [{"document_id": "gibtsnicht", "page": 1}]},
        headers=headers,
    )
    assert r.status_code == 400


def test_fremder_workspace_404(client, headers, fremde_headers):
    machine_id, document_id = _maschine(headers)
    body = {"text": "Geheim.", "belege": [{"document_id": document_id, "page": 1}]}
    note = client.post(f"/api/machines/{machine_id}/notes", json=body, headers=headers).json()
    assert client.get(f"/api/machines/{machine_id}/notes", headers=fremde_headers).status_code == 404
    url = f"/api/machines/{machine_id}/notes/{note['id']}"
    assert client.patch(url, json={}, headers=fremde_headers).status_code == 404
    assert client.delete(url, headers=fremde_headers).status_code == 404
    assert len(client.get(f"/api/machines/{machine_id}/notes", headers=headers).json()) == 1


def test_lerne_speichert_nur_belegte_saetze(client, headers, monkeypatch):
    from app.tenancy import reset_workspace, set_workspace
    from app.wissen import dienst

    machine_id, document_id = _maschine(headers)
    antwort = '[{"text": "Belegt.", "belege": [1]}, {"text": "Unbelegt.", "belege": []}]'
    monkeypatch.setattr(dienst, "frage_modell", lambda *a, **k: antwort)
    quellen = [{"document_id": document_id, "filename": "01_Plan.pdf", "page": 2}]
    token = set_workspace(WS)
    try:
        n = dienst.lerne(
            machine_id,
            "m",
            "FB-01",
            [{"question": "q", "answer_md": "a", "sources": quellen}],
            max_saetze=5,
            quelle="lauf",
            run_id="r1",
            session_id="run:r1",
        )
    finally:
        reset_workspace(token)
    assert n == 1
    notes = client.get(f"/api/machines/{machine_id}/notes", headers=headers).json()
    assert [(x["text"], x["quelle"], x["run_id"]) for x in notes] == [("Belegt.", "lauf", "r1")]


def test_lernen_nach_chat_wirft_nie(client, headers, monkeypatch):
    from app.wissen import dienst

    machine_id, document_id = _maschine(headers)

    def kaputt(*a, **k):
        raise ConnectionError("Modell weg")

    monkeypatch.setattr(dienst, "frage_modell", kaputt)
    refs = [{"document_id": document_id, "filename": "01_Plan.pdf", "page": 1}]
    dienst.lerne_aus_chat(machine_id, WS, "m", "Frage", "Antwort", refs, "c1")
    assert client.get(f"/api/machines/{machine_id}/notes", headers=headers).json() == []


def test_chat_kontext_enthaelt_gelernte_saetze(client, headers):
    from app.agent.prompts import system_prompt_for
    from app.api.chat import machine_scope
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    machine_id, document_id = _maschine(headers)
    client.post(
        f"/api/machines/{machine_id}/notes",
        json={"text": "Gesperrter Satz.", "belege": [{"document_id": document_id, "page": 1}]},
        headers=headers,
    )
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            _, kontext = machine_scope(session, machine_id)
    finally:
        reset_workspace(token)
    assert kontext["wissen"] == ["Gesperrter Satz."]
    assert "- Gesperrter Satz." in system_prompt_for({"machine": kontext})
