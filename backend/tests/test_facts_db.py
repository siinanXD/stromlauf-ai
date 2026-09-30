"""Befundkarte gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): Abschnitte aus Tabellen-Dokumenten.

Der Index fuehrt ein Kennzeichen je Seite und Abschnitt einmal, mit dem Kontext des ersten Funds (`tag_rows`).
Weitere Zeilen mit demselben Kennzeichen kommen nur ueber den ganzen Abschnitt aus `chunks` in die Karte.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "facts-test-secret-0123456789abcdefgh"
WS = "ws-facts-test"
# 03_Klemmenplan_FB-01.csv; der Index fuehrt -X2:3a als -X2:3A (Schreibweise von normalize_tag)
ROW_3A = "| -X2 | -X2:3a | -K3:14 | -K1:A1 / -K2:A1 (ueber -A1.2) | +24 V freigegeben | /4.4 |"
BRIDGE = "| -X5 | -X5:1 | -X2:3a | -S7:13 | Freigabe Tippen | /4.6 |"


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


def _wipe_workspace() -> None:
    """Quellen des Test-Workspace loeschen (Cascade: Dokumente, Chunks, Index)."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import KnowledgeSource
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            for source in session.scalars(select(KnowledgeSource)).all():
                session.delete(source)
    finally:
        reset_workspace(token)


@pytest.fixture(scope="module")
def world(client):
    """Klemmenplan mit zwei Zeilen zu -X2:3a, im Index nur die erste. Raeumt vorher und hinterher auf."""
    from app.auth import issue_token
    from app.config import get_settings
    from app.db import session_scope
    from app.models import (
        Chunk,
        Document,
        KnowledgeSource,
        TagOccurrence,
        User,
        Workspace,
        WorkspaceMember,
    )
    from app.tenancy import reset_workspace, set_workspace

    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
        session.merge(User(id=f"user-{WS}", email=f"{WS}@facts-test.de"))
        session.merge(WorkspaceMember(workspace_id=WS, user_id=f"user-{WS}", role="admin"))
    access, _ = issue_token(
        user_id=f"user-{WS}",
        email=f"{WS}@facts-test.de",
        workspace_id=WS,
        role="admin",
        secret=SECRET,
        hours=1,
    )
    _wipe_workspace()

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Befundkarte-Test")
            session.add(source)
            session.flush()
            plan = Document(
                source_id=source.id,
                filename="03_Klemmenplan.csv",
                storage_path="/nirgends/klemmenplan.csv",
                doc_type="terminal_plan",
                status="ready",
            )
            session.add(plan)
            session.flush()
            session.add(
                TagOccurrence(
                    document_id=plan.id,
                    source_id=source.id,
                    tag="-X2:3A",
                    tag_type="terminal",
                    page=None,
                    context=ROW_3A,
                )
            )
            session.add(
                Chunk(
                    document_id=plan.id,
                    source_id=source.id,
                    page=None,
                    kind="text",
                    section="Klemmenplan",
                    content=f"{ROW_3A}\n{BRIDGE}",
                    embedding=[0.0] * get_settings().embedding_dim,
                )
            )
            source_id = source.id
    finally:
        reset_workspace(token)
    yield {"headers": {"Authorization": f"Bearer {access}"}, "source_id": source_id}
    _wipe_workspace()


def test_abschnitt_mit_kleinbuchstaben_bringt_die_zweite_zeile_in_die_karte(client, world):
    response = client.get(
        "/api/facts",
        params={"tag": "-X2:3a", "source_ids": [world["source_id"]]},
        headers=world["headers"],
    )
    assert response.status_code == 200, response.text
    rows = {row["label"]: [v["text"] for v in row["values"]] for row in response.json()["rows"]}
    # /4.6 und -X5:1 stehen nur in der Bruecken-Zeile, die der Index nicht fuehrt
    assert rows == {"Stromlaufplan": ["/4.4", "/4.6"], "Klemmen": ["-X2:3A", "-X5:1"]}
