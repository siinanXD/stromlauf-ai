"""Einbauort am Schaltschrankbild (SIN-1220) gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    saved = {key: os.environ.get(key) for key in ("DATA_DIR", "JWT_SECRET")}
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ.pop("JWT_SECRET", None)
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def machine(client, tmp_path):
    """Halle -> Maschine mit einem alten Schrankbild ohne Einbauort in default; loescht hinterher die Halle."""
    from PIL import Image

    from app.db import session_scope
    from app.models import CabinetImage, Hall, Machine
    from app.tenancy import reset_workspace, set_workspace

    image = tmp_path / "alt.png"
    Image.new("RGB", (40, 30), "white").save(image)
    token = set_workspace("default")
    try:
        with session_scope() as session:
            hall = Hall(name="Halle Einbauort-Test")
            session.add(hall)
            session.flush()
            row = Machine(hall_id=hall.id, name="Presse E", machine_type="main")
            session.add(row)
            session.flush()
            session.add(
                CabinetImage(
                    machine_id=row.id,
                    title="Altes Foto",
                    image_path=str(image),
                    width=40,
                    height=30,
                )
            )
            hall_id, machine_id = hall.id, row.id
    finally:
        reset_workspace(token)
    yield machine_id
    token = set_workspace("default")
    try:
        with session_scope() as session:
            session.delete(session.get(Hall, hall_id))
    finally:
        reset_workspace(token)


def _png() -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_einbauort_anlegen_aendern_zuruecknehmen(client, machine):
    antwort = client.post(
        f"/api/machines/{machine}/cabinets",
        files={"file": ("schrank.png", _png(), "image/png")},
        data={"title": "Hauptschrank", "location_code": " +ST1 "},
    )
    assert antwort.status_code == 201
    cabinet = antwort.json()
    assert cabinet["location_code"] == "+ST1"

    geaendert = client.patch(f"/api/cabinets/{cabinet['id']}", json={"location_code": "+ST2"})
    assert geaendert.status_code == 200
    assert geaendert.json()["location_code"] == "+ST2"
    assert geaendert.json()["title"] == "Hauptschrank"  # nur genannte Felder aendern sich

    assert (
        client.patch(f"/api/cabinets/{cabinet['id']}", json={"location_code": None}).json()[
            "location_code"
        ]
        is None
    )
    assert (
        client.patch("/api/cabinets/gibts-nicht", json={"location_code": "+ST1"}).status_code == 404
    )


def test_alte_fotos_ohne_einbauort_bleiben_gueltig(client, machine):
    schraenke = client.get(f"/api/machines/{machine}").json()["cabinets"]
    assert [(c["title"], c["location_code"]) for c in schraenke] == [("Altes Foto", None)]
