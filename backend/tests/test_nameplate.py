"""Typenschild lesen und mit der Stueckliste vergleichen (SIN-982): Modell gemockt, kein Netz, keine Datenbank."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import Settings
from app.ingestion import cabinet_vision
from app.llm import MissingKeyError
from app.werk.nameplate import PASST, UNKLAR, WEICHT_AB, compare

ANTWORT = (
    'Hier das Ergebnis: {"manufacturer": "Siemens", "order_number": "3RT2026-1BB40", '
    '"type": "SIRIUS 3RT2", "confidence": 0.85}'
)
STUECKLISTE = "-K1 | Schütz 3RT2026-1BB40 | Siemens | 1 Stk"


class _FakeLLM:
    last_messages = None

    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, messages, config=None):
        _FakeLLM.last_messages = messages
        return SimpleNamespace(content=ANTWORT)


@pytest.fixture
def bild(tmp_path) -> Path:
    path = tmp_path / "schrank.png"
    Image.new("RGB", (400, 300), "white").save(path)
    return path


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, vision_model="claude-sonnet-5", anthropic_api_key="sk-ant", **kwargs)


def test_antwort_wird_geparst(monkeypatch, bild):
    monkeypatch.setattr(cabinet_vision, "get_settings", lambda: _settings())
    monkeypatch.setattr(cabinet_vision, "make_chat_model", _FakeLLM)
    plate = cabinet_vision.read_nameplate(bild, (0.2, 0.2, 0.3, 0.3))
    assert plate == {
        "manufacturer": "Siemens",
        "order_number": "3RT2026-1BB40",
        "type": "SIRIUS 3RT2",
        "confidence": 0.85,
    }
    assert any(block.get("type") == "text" for block in _FakeLLM.last_messages[0].content)


def test_nicht_lesbares_bleibt_leer():
    plate = cabinet_vision.parse_nameplate('{"manufacturer": null, "order_number": null, "confidence": "x"}')
    assert plate == {"manufacturer": "", "order_number": "", "type": "", "confidence": 0.0}


def test_antwort_ohne_json_ist_ein_fehler():
    with pytest.raises(ValueError):
        cabinet_vision.parse_nameplate("Ich kann nichts erkennen.")


def test_fehlender_schluessel_wirft_missing_key(monkeypatch, bild):
    settings = Settings(
        _env_file=None, vision_model="openai:gpt-5", anthropic_api_key="sk-ant", openai_api_key=None
    )
    monkeypatch.setattr(cabinet_vision, "get_settings", lambda: settings)
    with pytest.raises(MissingKeyError, match="OPENAI_API_KEY"):
        cabinet_vision.read_nameplate(bild, (0.0, 0.0, 1.0, 1.0))


def test_ausschnitt_liegt_im_bild(bild):
    from io import BytesIO

    png = cabinet_vision.crop_png(bild, 0.9, 0.9, 0.3, 0.3)
    with Image.open(BytesIO(png)) as crop:
        assert 0 < crop.width <= 400 and 0 < crop.height <= 300


def test_bestellnummer_in_stueckliste_passt():
    plate = {"manufacturer": "Siemens", "order_number": "3RT2026 1BB40"}
    result = compare(plate, STUECKLISTE)
    assert result["status"] == PASST
    assert result["manufacturer_found"] is True


def test_andere_bestellnummer_weicht_ab():
    result = compare({"manufacturer": "Siemens", "order_number": "3RT2027-1BB40"}, STUECKLISTE)
    assert result["status"] == WEICHT_AB
    assert result["order_number_found"] is False


def test_ohne_zeile_oder_nummer_ist_es_unklar():
    assert compare({"order_number": "3RT2026-1BB40"}, None)["status"] == UNKLAR
    assert compare({"order_number": ""}, STUECKLISTE)["status"] == UNKLAR
