"""Korrekturen am Maschinenmodell (SIN-1216) gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "map-override-test-secret-0123456789"
WS = "ws-map-override-test"
WS_FREMD = "ws-map-override-fremd"
BOM_ZEILEN = "Kennzeichen,Bezeichnung,Ort\n-K1,Schütz Hauptantrieb,+ST1\n-F2,Motorschutz Pumpe,+ST1\n"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Umgebung beim Abbau zurueckgeben, sonst erben spaetere Tests Secret und DATA_DIR dieses Moduls
    saved = {key: os.environ.get(key) for key in ("DATA_DIR", "JWT_SECRET")}
    os.environ["JWT_SECRET"] = SECRET
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    try:
        with TestClient(app) as client:
            yield client
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def _wipe(workspace_id: str) -> None:
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import KnowledgeSource, Machine
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(workspace_id)
    try:
        with session_scope() as session:
            for model in (Machine, KnowledgeSource):
                for row in session.scalars(select(model)).all():
                    session.delete(row)
    finally:
        reset_workspace(token)


def _login(workspace_id: str) -> dict:
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import User, Workspace, WorkspaceMember

    with session_scope() as session:
        session.merge(Workspace(id=workspace_id, name=workspace_id))
        session.merge(User(id=f"user-{workspace_id}", email=f"{workspace_id}@map-test.de"))
        session.merge(WorkspaceMember(workspace_id=workspace_id, user_id=f"user-{workspace_id}", role="admin"))
    access, _ = issue_token(
        user_id=f"user-{workspace_id}",
        email=f"{workspace_id}@map-test.de",
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


@pytest.fixture
def maschine(client, headers, tmp_path):
    """Maschine mit einer Stückliste (CSV) und deren Kennzeichen-Index; (machine_id, document_id)."""
    from app.db import session_scope
    from app.models import (
        DocStatus,
        Document,
        Hall,
        KnowledgeSource,
        Machine,
        TagOccurrence,
        TagType,
    )
    from app.tenancy import reset_workspace, set_workspace

    datei = tmp_path / "stueckliste.csv"
    datei.write_text(BOM_ZEILEN, encoding="utf-8")
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            quelle = KnowledgeSource(name="Quelle")
            halle = Hall(name="Halle")
            session.add_all([quelle, halle])
            session.flush()
            dokument = Document(
                source_id=quelle.id,
                filename=datei.name,
                storage_path=str(datei),
                doc_type="bom",
                status=DocStatus.READY,
            )
            maschine = Machine(hall_id=halle.id, name="FB-01", source_id=quelle.id)
            session.add_all([dokument, maschine])
            session.flush()
            for tag, zeile in (("-K1", "| -K1 | Schütz Hauptantrieb | +ST1 |"), ("-F2", "| -F2 | Motorschutz Pumpe | +ST1 |")):
                session.add(
                    TagOccurrence(
                        document_id=dokument.id,
                        source_id=quelle.id,
                        tag=tag,
                        tag_type=TagType.DEVICE,
                        context=zeile,
                    )
                )
            return maschine.id, dokument.id
    finally:
        reset_workspace(token)


def _teile(client, headers, machine_id) -> dict[str, tuple[str, str]]:
    karte = client.get(f"/api/machines/{machine_id}/map", headers=headers).json()
    return {p["tag"]: (z["code"], p["label"]) for z in karte["zones"] for p in z["parts"]}


def test_korrigieren_und_zuruecknehmen(client, headers, maschine):
    machine_id, _ = maschine
    assert _teile(client, headers, machine_id) == {"-K1": ("+ST1", "Schütz Hauptantrieb"), "-F2": ("+ST1", "Motorschutz Pumpe")}

    antwort = client.patch(
        f"/api/machines/{machine_id}/map/parts/-K1",
        json={"label": "Hauptschütz", "zone_code": "+BP1"},
        headers=headers,
    )
    assert antwort.status_code == 200
    assert antwort.json() == {
        "machine_id": machine_id,
        "tag": "-K1",
        "zone_code": "+BP1",
        "label": "Hauptschütz",
        "hidden": False,
    }
    assert _teile(client, headers, machine_id)["-K1"] == ("+BP1", "Hauptschütz")

    # nur genannte Felder ändern sich; null nimmt die Zone zurück, die Bezeichnung bleibt
    client.patch(f"/api/machines/{machine_id}/map/parts/-K1", json={"zone_code": None}, headers=headers)
    assert _teile(client, headers, machine_id)["-K1"] == ("+ST1", "Hauptschütz")

    # kleingeschrieben und ohne Minus landet auf demselben Schlüssel; ausblenden
    client.patch(f"/api/machines/{machine_id}/map/parts/f2", json={"hidden": True}, headers=headers)
    assert "-F2" not in _teile(client, headers, machine_id)

    assert client.delete(f"/api/machines/{machine_id}/map/parts/-K1", headers=headers).status_code == 204
    assert client.delete(f"/api/machines/{machine_id}/map/parts/-K1", headers=headers).status_code == 204
    # letzte Korrektur zurückgenommen -> keine Zeile mehr
    client.patch(f"/api/machines/{machine_id}/map/parts/-F2", json={"hidden": False}, headers=headers)
    assert _teile(client, headers, machine_id) == {"-K1": ("+ST1", "Schütz Hauptantrieb"), "-F2": ("+ST1", "Motorschutz Pumpe")}


def test_unbekanntes_teil_404(client, headers, maschine):
    machine_id, _ = maschine
    adresse = f"/api/machines/{machine_id}/map/parts/-Z9"
    assert client.patch(adresse, json={"hidden": True}, headers=headers).status_code == 404
    assert client.patch("/api/machines/gibts-nicht/map/parts/-K1", json={"hidden": True}, headers=headers).status_code == 404


def test_fremder_workspace_404(client, headers, fremde_headers, maschine):
    machine_id, _ = maschine
    client.patch(f"/api/machines/{machine_id}/map/parts/-K1", json={"label": "Mein Schütz"}, headers=headers)
    adresse = f"/api/machines/{machine_id}/map/parts/-K1"
    assert client.patch(adresse, json={"hidden": True}, headers=fremde_headers).status_code == 404
    assert client.delete(adresse, headers=fremde_headers).status_code == 404
    assert client.get(f"/api/machines/{machine_id}/map", headers=fremde_headers).status_code == 404
    assert _teile(client, headers, machine_id)["-K1"] == ("+ST1", "Mein Schütz")  # unberührt


def test_korrektur_ueberlebt_neu_verarbeiten(client, headers, maschine, monkeypatch):
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import session_scope
    from app.models import Document, TagOccurrence
    from app.tenancy import reset_workspace, set_workspace

    class Nullvektoren:
        def embed_documents(self, texts):
            return [[0.0] * get_settings().embedding_dim for _ in texts]

    monkeypatch.setattr("app.ingestion.pipeline.embeddings", Nullvektoren())
    machine_id, document_id = maschine
    client.patch(
        f"/api/machines/{machine_id}/map/parts/-K1",
        json={"label": "Hauptschütz", "zone_code": "+BP1"},
        headers=headers,
    )
    client.patch(f"/api/machines/{machine_id}/map/parts/-F2", json={"hidden": True}, headers=headers)

    def index_ids(session) -> set[int]:
        return set(session.scalars(select(TagOccurrence.id).where(TagOccurrence.document_id == document_id)))

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            vorher = index_ids(session)
        assert client.post(f"/api/documents/{document_id}/reingest", headers=headers).status_code == 200
        with session_scope() as session:
            dokument = session.get(Document, document_id)
            assert dokument.status == "ready", dokument.error
            nachher = index_ids(session)
        # der Index wurde ersetzt (neue Zeilen-IDs), die Korrektur nicht
        assert nachher and not nachher & vorher
    finally:
        reset_workspace(token)
    assert _teile(client, headers, machine_id) == {"-K1": ("+BP1", "Hauptschütz")}


def _schraenke_st1_st2(machine_id: str, tmp_path) -> None:
    """Zwei Schränke mit Einbauort, beide zeigen -K1; braucht den gesetzten Workspace."""
    from PIL import Image

    from app.db import session_scope
    from app.models import CabinetHotspot, CabinetImage

    bild = tmp_path / "schrank.png"
    Image.new("RGB", (40, 30), "white").save(bild)
    with session_scope() as session:
        for code in ("+ST1", "+ST2"):
            schrank = CabinetImage(machine_id=machine_id, title=f"Schrank {code}", location_code=code, image_path=str(bild), width=40, height=30)
            session.add(schrank)
            session.flush()
            session.add(CabinetHotspot(cabinet_id=schrank.id, tag="-K1", label="", x=0.1, y=0.1, w=0.1, h=0.1))


def _beleg_zonen(machine_id: str) -> list[str | None]:
    from app.api.answer_meta import build_meta
    from app.db import session_scope
    from app.models import Machine

    with session_scope() as session:
        quelle = session.get(Machine, machine_id).source_id
        meta = build_meta(session, answer="Prüfe -K1.", citations=[], source_ids=[quelle], machine_id=machine_id)
    return [e["zone"] for e in meta["evidence"] if e["kind"] == "cabinet"]


def test_ausgeblendetes_teil_behaelt_einbauort_fuer_schrankbelege(client, headers, maschine, tmp_path):
    """Review zu SIN-1220: -K1 sitzt in +ST1. Ausblenden im Modell darf den Schrank +ST2 nicht als Beleg zulassen."""
    from app.tenancy import reset_workspace, set_workspace

    machine_id, _ = maschine
    token = set_workspace(WS)
    try:
        _schraenke_st1_st2(machine_id, tmp_path)
        assert _beleg_zonen(machine_id) == ["+ST1"]
        assert client.patch(f"/api/machines/{machine_id}/map/parts/-K1", json={"hidden": True}, headers=headers).status_code == 200
        assert _beleg_zonen(machine_id) == ["+ST1"]
    finally:
        reset_workspace(token)


@pytest.mark.parametrize(("eingabe", "schrank"), [(" +ST1 ", "+ST1"), (" +ST2 ", "+ST2")])
def test_korrigierter_einbauort_mit_leerzeichen_laesst_keinen_fremden_schrank_zu(client, headers, maschine, tmp_path, eingabe, schrank):
    """Review zu SIN-1220: die Korrektur bleibt wie getippt stehen, zählt aber als Einbauort, auch ausgeblendet."""
    from app.tenancy import reset_workspace, set_workspace

    machine_id, _ = maschine
    adresse = f"/api/machines/{machine_id}/map/parts/-K1"
    token = set_workspace(WS)
    try:
        _schraenke_st1_st2(machine_id, tmp_path)
        assert client.patch(adresse, json={"zone_code": eingabe}, headers=headers).status_code == 200
        assert _teile(client, headers, machine_id)["-K1"][0] == eingabe
        assert _beleg_zonen(machine_id) == [schrank]
        assert client.patch(adresse, json={"hidden": True}, headers=headers).status_code == 200
        assert _beleg_zonen(machine_id) == [schrank]
    finally:
        reset_workspace(token)
