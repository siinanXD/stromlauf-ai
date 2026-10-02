"""Konfig-Hygiene gegen Postgres (Issue #50): Ein fehlender Vision-Schluessel ist ein 400 mit seinem Namen, eine
.scl-Datei wird ueber den Upload READY. Offener Modus im Workspace default; jeder Test loescht genau seine Zeilen."""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "FB10_Foerderband.scl"


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
def vision_target(client, tmp_path):
    """Halle -> Maschine mit Schrankbild (ein kleines PNG) in default; loescht hinterher die Halle."""
    from PIL import Image

    from app.db import session_scope
    from app.models import CabinetImage, Hall, Machine
    from app.tenancy import reset_workspace, set_workspace

    image = tmp_path / "bild.png"
    Image.new("RGB", (80, 60), "white").save(image)
    token = set_workspace("default")
    try:
        with session_scope() as session:
            hall = Hall(name="Halle Vision-Schluessel")
            session.add(hall)
            session.flush()
            machine = Machine(hall_id=hall.id, name="Presse V", machine_type="main")
            session.add(machine)
            session.flush()
            cabinet = CabinetImage(
                machine_id=machine.id, title="Schrank", image_path=str(image), width=80, height=60
            )
            session.add(cabinet)
            session.flush()
            hall_id, cabinet_id = hall.id, cabinet.id
    finally:
        reset_workspace(token)
    yield cabinet_id
    token = set_workspace("default")
    try:
        with session_scope() as session:
            session.delete(session.get(Hall, hall_id))
    finally:
        reset_workspace(token)


def test_fehlender_vision_schluessel_ist_ein_400_mit_seinem_namen(
    client, vision_target, monkeypatch
):
    from app.config import Settings
    from app.ingestion import cabinet_vision

    settings = Settings(
        _env_file=None, vision_model="openai:gpt-5", anthropic_api_key="sk-ant", openai_api_key=None
    )
    monkeypatch.setattr(cabinet_vision, "get_settings", lambda: settings)
    url = f"/api/cabinets/{vision_target}/detect"
    response = client.post(url)
    assert response.status_code == 400, (url, response.text)
    assert "OPENAI_API_KEY" in response.json()["detail"], url


def test_scl_upload_wird_ready_und_chunks_tragen_den_dateinamen(client, monkeypatch):
    from app.config import get_settings
    from app.ingestion import pipeline

    dim = get_settings().embedding_dim
    texts: list[str] = []

    class _Recorder:
        def embed_documents(self, batch: list[str]) -> list[list[float]]:
            texts.extend(batch)
            return [[0.0] * dim for _ in batch]

    monkeypatch.setattr(pipeline, "embeddings", _Recorder())
    data = FIXTURE.read_bytes()
    detected = client.post(
        "/api/documents/detect", files={"file": (FIXTURE.name, data, "text/plain")}
    )
    assert detected.json()["doc_type"] == "plc_program"

    source = client.post("/api/sources", json={"name": "SCL-Upload-Test"}).json()
    try:
        response = client.post(
            f"/api/sources/{source['id']}/documents",
            files={"file": (FIXTURE.name, data, "text/plain")},
            data={"doc_type": "auto"},
        )
        assert response.status_code == 201, response.text
        (document,) = client.get(f"/api/sources/{source['id']}/documents").json()
        assert (document["status"], document["doc_type"], document["error"]) == (
            "ready",
            "plc_program",
            None,
        )
        # jeder Chunk kommt mit dem Dateinamen vorne in die Suche (pipeline._embedding_text)
        assert texts and all(text.startswith(FIXTURE.name) for text in texts)
    finally:
        client.delete(f"/api/sources/{source['id']}")
