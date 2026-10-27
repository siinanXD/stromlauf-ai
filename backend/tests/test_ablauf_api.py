"""Ablauf-API gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): /api/runs mit dem Foerderband."""

import os
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "ablauf-test-secret-0123456789abcdefgh"
WS = "ws-ablauf-test"
WS_FREMD = "ws-ablauf-fremd"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "foerderband"


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
        session.merge(User(id=f"user-{workspace_id}", email=f"{workspace_id}@ablauf-test.de"))
        session.merge(
            WorkspaceMember(workspace_id=workspace_id, user_id=f"user-{workspace_id}", role="admin")
        )
    access, _ = issue_token(
        user_id=f"user-{workspace_id}",
        email=f"{workspace_id}@ablauf-test.de",
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


def _warte(client, headers, run_id: str, timeout: float = 600) -> dict:
    deadline = time.time() + timeout
    run: dict = {}
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}", headers=headers).json()
        if run["status"] in {"fertig", "fehler"}:
            break
        time.sleep(2)
    return run


def test_lauf_mit_foerderband_wird_fertig(client, headers, monkeypatch):
    def antwort(*a, **k):
        time.sleep(0.1)
        return "Förderband mit zwei Bändern.", []

    monkeypatch.setattr("app.ablauf.lauf.beantworte", antwort)
    files = [("files", (p.name, p.read_bytes())) for p in sorted(EXAMPLES.glob("0[1-6]_*"))]
    created = client.post("/api/runs", files=files, data={"name": "FB-01 Test"}, headers=headers)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    assert created.json()["steps"][0]["status"] == "fertig"
    assert created.json()["steps"][0]["output"].startswith("6 Dateien: ")
    run = _warte(client, headers, run_id)
    assert run["status"] == "fertig", run
    assert [s["status"] for s in run["steps"]] == ["fertig"] * 7
    from app.db import session_scope
    from app.models import Run

    with session_scope() as session:
        assert session.get(Run, run_id).steps[1]["result"]["dokumente"] == 6
    assert run["result"]["machine_id"]
    assert run["result"]["profile"]["doc_types"]
    assert run["result"]["map_counts"]["parts"] > 0
    assert run["result"]["answers"][0]["answer_md"].startswith("Förderband")
    assert run["result"]["answers"][0]["dauer_s"] > 0
    assert client.get("/api/runs", headers=headers).json()[0]["id"] == run_id


def test_zeiten_endpunkt(client, headers, fremde_headers, monkeypatch):
    monkeypatch.setattr("app.ablauf.lauf.ingest_document", lambda document_id: None)
    monkeypatch.setattr("app.ablauf.lauf.beantworte", lambda *a, **k: ("Antwort.", []))
    ids = []
    for name in ("a.md", "b.md"):
        created = client.post("/api/runs", files=[("files", (name, b"# Doku"))], headers=headers)
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    eigene = [_warte(client, headers, i, timeout=120) for i in ids]
    assert all(r["status"] in {"fertig", "fehler"} for r in eigene), eigene
    lesen_fertig = sum(
        1
        for r in eigene
        if next(s for s in r["steps"] if s["key"] == "lesen")["status"] == "fertig"
    )
    antwort = client.get("/api/runs/zeiten", headers=headers)
    assert antwort.status_code == 200, antwort.text
    zeiten = antwort.json()
    assert 2 <= zeiten["laeufe"] <= 50
    assert zeiten["schritte"]["lesen"]["anzahl"] >= lesen_fertig
    assert {"gesamt", "fragen"} <= zeiten.keys()
    assert "langsamster_trace_url" in zeiten["gesamt"]
    fremd = client.get("/api/runs/zeiten", headers=fremde_headers)
    assert fremd.status_code == 200 and fremd.json()["laeufe"] == 0


def test_ohne_datei_400_und_keine_quelle(client, headers):
    before = len(client.get("/api/sources", headers=headers).json())
    assert client.post("/api/runs", files=[], data={}, headers=headers).status_code in {400, 422}
    assert len(client.get("/api/sources", headers=headers).json()) == before


def test_falsche_endung_415_und_keine_quelle(client, headers):
    before = len(client.get("/api/sources", headers=headers).json())
    r = client.post("/api/runs", files=[("files", ("x.exe", b"nope"))], headers=headers)
    assert r.status_code == 415
    assert len(client.get("/api/sources", headers=headers).json()) == before


def test_fremder_workspace_404(client, headers, fremde_headers, monkeypatch):
    monkeypatch.setattr("app.ablauf.lauf.ingest_document", lambda document_id: None)
    created = client.post("/api/runs", files=[("files", ("a.md", b"# Doku -K1"))], headers=headers)
    run_id = created.json()["id"]
    assert client.get(f"/api/runs/{run_id}", headers=fremde_headers).status_code == 404
    assert client.get(f"/api/runs/{run_id}", headers=headers).status_code == 200
    _warte(client, headers, run_id, timeout=60)


def test_fehler_im_lesen_stoppt_lauf(client, headers, monkeypatch):
    def kaputt(document_id):
        from app.db import session_scope
        from app.models import Document

        with session_scope() as s:
            d = s.get(Document, document_id)
            d.status = "failed"
            d.error = "Kein Text im Dokument gefunden"

    monkeypatch.setattr("app.ablauf.lauf.ingest_document", kaputt)
    created = client.post("/api/runs", files=[("files", ("a.md", b"# Doku"))], headers=headers)
    run = _warte(client, headers, created.json()["id"], timeout=60)
    assert run["status"] == "fehler"
    assert run["steps"][1]["status"] == "fehler" and "Kein Text" in run["steps"][1]["error"]
    assert all(s["status"] == "wartet" for s in run["steps"][2:])


def test_neustart_bricht_haengende_laeufe_ab(client):
    from app.ablauf.lauf import brich_haengende_laeufe_ab
    from app.ablauf.schritte import beende, neue_schritte, starte
    from app.db import session_scope
    from app.models import KnowledgeSource, Run
    from app.tenancy import reset_workspace, set_workspace

    _login(WS)
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="haengt")
            session.add(source)
            session.flush()
            steps = starte(beende(neue_schritte(), "hochladen", "t0", "ok"), "lesen", "t1", "x")
            run = Run(name="haengt", source_id=source.id, steps=steps, model="m")
            session.add(run)
            session.flush()
            run_id = run.id
    finally:
        reset_workspace(token)

    with session_scope() as session:  # ohne Workspace-Kontext, wie im lifespan
        assert brich_haengende_laeufe_ab(session) >= 1
    with session_scope() as session:
        run = session.get(Run, run_id)
        assert run.status == "fehler" and run.error == "Backend neu gestartet"
        assert run.finished_at is not None
        assert run.steps[1]["status"] == "fehler" and run.steps[2]["status"] == "wartet"
        assert brich_haengende_laeufe_ab(session) == 0
    _wipe(WS)


def test_gruppen_vorschlag(client, headers):
    beispiele = Path(__file__).resolve().parents[2] / "examples"
    dateien = [
        {"name": p.name, "pfad": p.name}
        for ordner in ("foerderband", "umroller", "aufrollung")
        for p in sorted((beispiele / ordner).iterdir())
        if p.name != "README.md"
    ]
    assert len(dateien) == 20
    r = client.post("/api/runs/gruppen", json={"dateien": dateien}, headers=headers)
    assert r.status_code == 200, r.text
    daten = r.json()
    assert sorted(g["name"] for g in daten["gruppen"]) == ["FB-01", "PM1-AR", "UR-01"]
    assert daten["unzugeordnet"] == [] and daten["ignoriert"] == []


def test_parallele_laeufe_eine_halle(client, headers, monkeypatch):
    monkeypatch.setattr("app.ablauf.lauf.ingest_document", lambda document_id: None)
    monkeypatch.setattr("app.ablauf.lauf.beantworte", lambda *a, **k: ("Antwort.", []))
    ids = []
    for name in ("p1.md", "p2.md"):
        created = client.post("/api/runs", files=[("files", (name, b"# Doku"))], headers=headers)
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    laeufe = [_warte(client, headers, i, timeout=120) for i in ids]
    assert all(r["status"] in {"fertig", "fehler"} for r in laeufe), laeufe
    hallen = [h for h in client.get("/api/halls", headers=headers).json() if h["name"] == "Ablauf"]
    assert len(hallen) == 1
    from app.db import session_scope
    from app.models import Machine
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            maschinen = [session.get(Machine, r["result"]["machine_id"]) for r in laeufe]
            assert all(m is not None and m.hall_id == hallen[0]["id"] for m in maschinen)
    finally:
        reset_workspace(token)


def test_zu_viele_dateien_400(client, headers):
    before = len(client.get("/api/sources", headers=headers).json())
    files = [("files", (f"d{i}.md", b"# x")) for i in range(101)]
    r = client.post("/api/runs", files=files, headers=headers)
    assert r.status_code == 400 and "100" in r.json()["detail"]
    assert len(client.get("/api/sources", headers=headers).json()) == before
