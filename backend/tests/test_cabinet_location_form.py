"""location_code beim Schrank-Upload (SIN-1220): zu lang ist 422, bevor ein Bild entsteht.

Ohne Datenbank: nur der Router auf einer eigenen App, die Overrides enden also mit dem Test.
"""

from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api import plant
from app.db import get_session


class _Session:
    def __init__(self):
        self.added = []

    def get(self, _model, item_id):
        return SimpleNamespace(id=item_id)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        pass

    def refresh(self, item):
        item.id = "c1"
        item.created_at = datetime(2026, 11, 9)


@pytest.fixture
def upload(tmp_path, monkeypatch):
    """Sendet ein gueltiges PNG; zaehlt _store_image, die Bilder landen in tmp_path."""
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(plant, "_image_dir", lambda: images)
    stored = []
    store_image = plant._store_image

    def spy(file):
        stored.append(file.filename)
        return store_image(file)

    monkeypatch.setattr(plant, "_store_image", spy)
    session = _Session()
    app = FastAPI()
    app.include_router(plant.router)
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    buffer = BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="PNG")

    def send(**fields):
        return client.post(
            "/api/machines/m1/cabinets",
            files={"file": ("schrank.png", buffer.getvalue(), "image/png")},
            data=fields,
        )

    return SimpleNamespace(send=send, stored=stored, images=images, session=session)


def test_120_zeichen_werden_gespeichert(upload):
    response = upload.send(location_code="+" * 120)
    assert response.status_code == 201
    assert response.json()["location_code"] == "+" * 120
    assert len(upload.stored) == 1
    assert len(list(upload.images.iterdir())) == 1


def test_121_zeichen_422_ohne_bild_und_ohne_zeile(upload):
    response = upload.send(location_code="+" * 121)
    assert response.status_code == 422
    fehler = response.json()["detail"][0]
    assert fehler["loc"] == ["body", "location_code"]
    assert fehler["type"] == "string_too_long"
    assert upload.stored == []
    assert list(upload.images.iterdir()) == []
    assert upload.session.added == []


@pytest.mark.parametrize("fields", [{}, {"location_code": ""}, {"location_code": "   "}])
def test_ohne_einbauort_bleibt_er_leer(upload, fields):
    response = upload.send(**fields)
    assert response.status_code == 201
    assert response.json()["location_code"] is None
