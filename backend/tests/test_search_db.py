"""Globale Suche gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): Bausteine und Bauteilnamen (SIN-1462).

Vorher fand die Suche nur Kennzeichen-Praefixe. In der Demo lieferten `FB 10` und `Foerdermotor` "Keine Treffer",
obwohl beide im Index stehen (Chunks der AWL-Bausteine, Kontext der Stuecklistenzeile).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "search-test-secret-0123456789abcdefgh"
WS = "ws-search-test"


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
    """Hallen und Quellen des Test-Workspace loeschen (Cascade: Maschinen, Dokumente, Chunks, Index)."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import Hall, KnowledgeSource
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            for model in (Hall, KnowledgeSource):
                for row in session.scalars(select(model)).all():
                    session.delete(row)
    finally:
        reset_workspace(token)


@pytest.fixture(scope="module")
def world(client):
    """Foerderband mit Baustein FB 10, Motor -M1 (Stueckliste) und Schuetz -K1. Raeumt vorher und hinterher auf."""
    from app.auth import issue_token
    from app.config import get_settings
    from app.db import session_scope
    from app.models import (
        Chunk,
        Document,
        Hall,
        KnowledgeSource,
        Machine,
        TagOccurrence,
        User,
        Workspace,
        WorkspaceMember,
    )
    from app.tenancy import reset_workspace, set_workspace

    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
        session.merge(User(id=f"user-{WS}", email=f"{WS}@search-test.de"))
        session.merge(WorkspaceMember(workspace_id=WS, user_id=f"user-{WS}", role="admin"))
    access, _ = issue_token(
        user_id=f"user-{WS}", email=f"{WS}@search-test.de", workspace_id=WS, role="admin", secret=SECRET, hours=1
    )
    _wipe_workspace()

    zero = [0.0] * get_settings().embedding_dim
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Suche-Test")
            hall = Hall(name="Halle Test")
            session.add_all([source, hall])
            session.flush()
            session.add(Machine(hall_id=hall.id, name="FB-01", source_id=source.id))
            bom = Document(source_id=source.id, filename="02_Stueckliste.xlsx", storage_path="/nirgends/b.xlsx", doc_type="bom", status="ready")
            awl = Document(source_id=source.id, filename="04_SPS.awl", storage_path="/nirgends/p.awl", doc_type="plc_program", status="ready")
            session.add_all([bom, awl])
            session.flush()
            for tag, context in (
                ("-M1", "| -M1 | Foerdermotor 1,5 kW | +AN1 |"),
                ("-K1", "| -K1 | Schuetz vorwaerts | +ST1 |"),
                ("-K2", "| -K2 | Schuetz rueckwaerts | +ST1 |"),
            ):
                session.add(TagOccurrence(document_id=bom.id, source_id=source.id, tag=tag, tag_type="device", context=context))
            for section, kind in (
                ("FB 10 - Foerderband FB-01", "awl_block"),
                ("FB 10 - Foerderband FB-01 / NW 1 Freigabe", "awl_network"),
                ("FB 10 - Foerderband FB-01 / NW 2 Motor", "awl_network"),
                ("OB 1", "awl_block"),
                ("OB 1 / NW 1 Aufruf", "awl_network"),
            ):
                session.add(Chunk(document_id=awl.id, source_id=source.id, kind=kind, section=section, content=section, embedding=zero))
    finally:
        reset_workspace(token)
    yield {"headers": {"Authorization": f"Bearer {access}"}}
    _wipe_workspace()


def _hits(client, world, q: str) -> list[dict]:
    response = client.get("/api/tags/search", params={"q": q}, headers=world["headers"])
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("query", ["FB 10", "fb10", "FB 1"])
def test_baustein_wird_gefunden(client, world, query):
    hit = next(h for h in _hits(client, world, query) if h["tag"] == "FB 10")
    assert hit["tag_type"] == "plc_block"
    assert hit["occurrences"] == 2  # Netzwerke
    assert [m["name"] for m in hit["machines"]] == ["FB-01"]


def test_baustein_ohne_treffer_bleibt_leer(client, world):
    # "FB 107" ist kein Baustein (die Demo zeigt "FB 10" und daneben die Anzahl 7)
    assert [h for h in _hits(client, world, "FB 107") if h["tag_type"] == "plc_block"] == []


@pytest.mark.parametrize("query", ["Foerdermotor", "foerdermotor", "Fördermotor", "FÖRDERMOTOR"])
def test_bauteilname_findet_das_bauteil_auch_mit_umlaut(client, world, query):
    assert [h["tag"] for h in _hits(client, world, query)] == ["-M1"]


def test_bauteilname_findet_mehrere_bauteile(client, world):
    assert [h["tag"] for h in _hits(client, world, "Schütz")] == ["-K1", "-K2"]


def test_kennzeichen_bleiben_exakt_und_ziehen_keinen_freitext_nach(client, world):
    assert [h["tag"] for h in _hits(client, world, "-K1")] == ["-K1"]
    assert _hits(client, world, "-K12") == []
