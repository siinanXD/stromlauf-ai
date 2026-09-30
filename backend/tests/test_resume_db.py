"""Fortsetzen der Ingestion beim Start (lifespan in app/main.py) gegen Postgres; lokal STROMLAUF_DB_TESTS=1.

Lokal teilen sich Testlaeufe die Entwicklungsdatenbank mit dem Backend und mit Laeufen anderer Sitzungen.
Ein Testprozess darf beim Start deshalb keine Dokumente neu einreihen oder verarbeiten; das eine Backend
setzt nach einem Neustart weiter alle unterbrochenen Dokumente fort, ueber alle Workspaces.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

WORKSPACES = ("ws-resume-test-a", "ws-resume-test-b")


@pytest.fixture
def uncommitted(monkeypatch):
    """Alle Sitzungen des Tests laufen in einer Transaktion, die am Ende zurueckgerollt wird.

    Committete PENDING-Dokumente verarbeitet jeder Prozess, der in der Zeit mit Fortsetzen startet; so bleiben
    die Testdokumente fuer andere Prozesse unsichtbar, und hinterher bleibt keine Zeile zurueck.
    """
    from sqlalchemy.orm import sessionmaker

    from app import db

    db.init_db()  # Tabellen vor dem ersten Insert, auch auf einer frischen Datenbank
    connection = db.engine.connect()
    transaction = connection.begin()
    monkeypatch.setattr(
        db,
        "SessionLocal",
        sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"),
    )
    try:
        yield
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def interrupted(uncommitted, tmp_path):
    """Je Test-Workspace ein Dokument auf PENDING mit vorhandener Datei, wie nach einem Absturz.

    Liefert {Workspace: Dokument-id}.
    """
    from app.db import session_scope
    from app.models import DocStatus, Document, KnowledgeSource, Workspace
    from app.tenancy import reset_workspace, set_workspace

    upload = tmp_path / "plan.txt"
    upload.write_text("-K1 zieht an", encoding="utf-8")
    with session_scope() as session:
        for workspace in WORKSPACES:
            session.merge(Workspace(id=workspace, name=workspace))
    ids = {}
    for workspace in WORKSPACES:
        token = set_workspace(workspace)
        try:
            with session_scope() as session:
                source = KnowledgeSource(name="Neustart-Test")
                session.add(source)
                session.flush()
                document = Document(
                    source_id=source.id,
                    filename=upload.name,
                    storage_path=str(upload),
                    status=DocStatus.PENDING,
                )
                session.add(document)
                session.flush()
                ids[workspace] = document.id
        finally:
            reset_workspace(token)
    return ids


def _state(ids: dict[str, str]) -> dict[str, tuple[str, str, int]]:
    """(Status, Fortschritt, Anlaeufe) je Workspace aus der Datenbank."""
    from app.db import session_scope
    from app.models import Document
    from app.tenancy import reset_workspace, set_workspace

    state = {}
    for workspace, document_id in ids.items():
        token = set_workspace(workspace)
        try:
            with session_scope() as session:
                document = session.get(Document, document_id)
                state[workspace] = (document.status, document.progress, document.attempts)
        finally:
            reset_workspace(token)
    return state


@pytest.fixture
def start_app(uncommitted, tmp_path, monkeypatch):
    """Startet die App einmal (lifespan) und liefert, was sie angeboten bekam und fortsetzen wollte.

    plan_restart sieht alle Dokumente, aendert aber nur die der Test-Workspaces, damit ein Lauf, der
    faelschlich fortsetzt, keine fremden Zeilen sperrt; resume_in_background startet keinen Thread.
    """
    from fastapi.testclient import TestClient

    from app import main
    from app.config import get_settings
    from app.ingestion.resume import plan_restart

    seen: list[tuple[str, str]] = []
    resumed: list[str] = []

    def plan_own_only(documents):
        documents = list(documents)
        seen.extend((document.workspace_id, document.id) for document in documents)
        return plan_restart([d for d in documents if d.workspace_id in WORKSPACES])

    monkeypatch.setattr(main, "plan_restart", plan_own_only)
    monkeypatch.setattr(main, "resume_in_background", resumed.extend)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    def start() -> tuple[list[tuple[str, str]], list[str]]:
        get_settings.cache_clear()
        with TestClient(main.app):
            pass
        return seen, resumed

    yield start
    get_settings.cache_clear()


def test_testprozess_reiht_beim_start_nichts_neu_ein(interrupted, start_app):
    """Sonst verarbeitet ein Testlauf Uploads, die gerade das Backend oder ein anderer Lauf bearbeitet."""
    seen, resumed = start_app()

    assert (seen, resumed) == ([], [])
    assert _state(interrupted) == {workspace: ("pending", "", 0) for workspace in WORKSPACES}


def test_backend_setzt_unterbrochene_dokumente_aller_workspaces_fort(interrupted, start_app, monkeypatch):
    """Produktion (weder Umgebung noch .env setzen RESUME_INGESTION): nach einem Neustart wird alles neu eingereiht."""
    from app import main
    from app.config import Settings
    from app.ingestion.resume import REQUEUED

    monkeypatch.delenv("RESUME_INGESTION", raising=False)
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))
    _, resumed = start_app()

    assert sorted(resumed) == sorted(interrupted.values())
    assert _state(interrupted) == {workspace: ("pending", REQUEUED, 0) for workspace in WORKSPACES}
