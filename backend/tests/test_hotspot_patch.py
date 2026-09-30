"""Korrigierte Rahmen (MB-5): PATCH mit Geometrie macht den Hotspot manuell und bestaetigt (gegen Postgres)."""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ.pop("JWT_SECRET", None)
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


@pytest.fixture
def hotspot_id(client):
    """Halle -> Maschine -> Schrankbild -> Hotspot in default; loescht hinterher genau diese Halle.

    default haelt lokal die Demo-Daten: geloescht wird nur die eigene Halle (Cascade raeumt
    Maschine, Schrankbild und Hotspot mit), nichts sonst in diesem Workspace.
    """
    from app.db import session_scope
    from app.models import CabinetHotspot, CabinetImage, Hall, Machine
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace("default")  # offener Modus: alles im Standard-Workspace
    with session_scope() as session:
        hall = Hall(name="Halle H", description="")
        session.add(hall)
        session.flush()
        machine = Machine(hall_id=hall.id, name="Presse H", machine_type="main", description="")
        session.add(machine)
        session.flush()
        cabinet = CabinetImage(machine_id=machine.id, title="Schrank", image_path="/nirgends/schrank.png", width=800, height=600)
        session.add(cabinet)
        session.flush()
        hotspot = CabinetHotspot(cabinet_id=cabinet.id, tag="-K1", label="", kind="", x=0.2, y=0.3, w=0.1, h=0.12, confidence=0.7, origin="vision", confirmed=False)
        session.add(hotspot)
        session.flush()
        hall_id, created_id = hall.id, hotspot.id
    reset_workspace(token)
    yield created_id
    token = set_workspace("default")
    try:
        with session_scope() as session:
            session.delete(session.get(Hall, hall_id))
    finally:
        reset_workspace(token)


def test_rahmen_korrektur_setzt_manual_und_confirmed(client, hotspot_id):
    # nur Text aendern: Herkunft und Bestaetigung bleiben
    renamed = client.patch(f"/api/hotspots/{hotspot_id}", json={"label": "Hauptschütz"}).json()
    assert renamed["origin"] == "vision" and renamed["confirmed"] is False

    moved = client.patch(f"/api/hotspots/{hotspot_id}", json={"x": 0.22, "h": 0.125}).json()
    assert moved["x"] == pytest.approx(0.22) and moved["h"] == pytest.approx(0.125) and moved["y"] == pytest.approx(0.3)
    assert moved["origin"] == "manual" and moved["confirmed"] is True
    assert client.patch(f"/api/hotspots/{hotspot_id}", json={"x": 1.5}).status_code == 422
