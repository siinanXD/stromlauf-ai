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
    monkeypatch.setattr(
        "app.ablauf.lauf.beantworte", lambda *a, **k: ("Förderband mit zwei Bändern.", [])
    )
    files = [("files", (p.name, p.read_bytes())) for p in sorted(EXAMPLES.glob("0[1-6]_*"))]
    created = client.post("/api/runs", files=files, data={"name": "FB-01 Test"}, headers=headers)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    assert created.json()["steps"][0]["status"] == "fertig"
    assert created.json()["steps"][0]["output"].startswith("6 Dateien: ")
    run = _warte(client, headers, run_id)
    assert run["status"] == "fertig", run
    assert [s["status"] for s in run["steps"]] == ["fertig"] * 7
    assert run["result"]["machine_id"]
    assert run["result"]["profile"]["doc_types"]
    assert run["result"]["map_counts"]["parts"] > 0
    assert run["result"]["answers"][0]["answer_md"].startswith("Förderband")
    assert client.get("/api/runs", headers=headers).json()[0]["id"] == run_id


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
