"""Konfig-Hygiene (Issue #50): Sonnet als Standard, Schluesselpruefung je Provider, .scl als SPS-Quelle."""

from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "FB10_Foerderband.scl"
MODEL_VARS = ("CHAT_MODEL", "VISION_MODEL", "FLOW_MODEL_STRONG")


class _NoRows:
    def scalars(self, *_args, **_kwargs):
        return []


def test_standardmodelle_sind_sonnet_ohne_env(monkeypatch):
    for key in MODEL_VARS:
        monkeypatch.delenv(key, raising=False)
    from app.config import Settings

    settings = Settings(_env_file=None)
    assert settings.chat_model == "claude-sonnet-5" and settings.vision_model == "claude-sonnet-5"
    assert (
        settings.flow_model_strong == "claude-opus-5"
    )  # Schrittkette bleibt beim starken Modell (cost-model.md)


def test_schaetzung_rechnet_ohne_env_mit_sonnet(monkeypatch):
    for key in MODEL_VARS:
        monkeypatch.delenv(key, raising=False)
    from app import ledger
    from app.config import Settings

    # ohne lokale .env wie in der CI, sonst gewinnt ein dort gesetztes VISION_MODEL
    monkeypatch.setattr(ledger, "get_settings", lambda: Settings(_env_file=None))
    result = ledger.estimate(_NoRows(), pages=10, photos=1)
    assert (
        result["models"]["vision"] == "claude-sonnet-5"
        and result["models"]["chat"] == "claude-sonnet-5"
    )
    assert result["per_page_vision_cents"] == pytest.approx(
        ledger._list_cents("vision.page", "claude-sonnet-5"), rel=1e-6
    )
    assert result["per_page_vision_cents"] < ledger._list_cents("vision.page", "claude-opus-5")


def test_fehlender_schluessel_wird_je_provider_benannt():
    from app import llm

    only_openai = SimpleNamespace(anthropic_api_key=None, openai_api_key="sk-openai")
    only_anthropic = SimpleNamespace(anthropic_api_key="sk-ant", openai_api_key=None)
    assert llm.missing_key("openai:gpt-5", only_openai) is None
    assert llm.missing_key("claude-sonnet-5", only_openai) == "ANTHROPIC_API_KEY"
    assert llm.missing_key("gpt-5-mini", only_anthropic) == "OPENAI_API_KEY"
    with pytest.raises(ValueError):
        llm.missing_key("llama-3", only_openai)


def test_vision_hinweis_und_erkennung_folgen_dem_provider_des_modells(monkeypatch):
    from app import llm
    from app.ingestion import cabinet_vision, pipeline

    with_openai = SimpleNamespace(
        vision_model="openai:gpt-5", anthropic_api_key=None, openai_api_key="sk-openai"
    )
    without = SimpleNamespace(
        vision_model="openai:gpt-5", anthropic_api_key="sk-ant", openai_api_key=None
    )
    monkeypatch.setattr(pipeline, "get_settings", lambda: with_openai)
    assert pipeline.vision_skip_note() == ""
    monkeypatch.setattr(pipeline, "get_settings", lambda: without)
    assert pipeline.vision_skip_note() == "Vision-Analyse uebersprungen: OPENAI_API_KEY fehlt"

    # eigener Fehlertyp, damit die Endpunkte daraus ein 400 mit dem Namen machen (nicht 502)
    monkeypatch.setattr(cabinet_vision, "get_settings", lambda: without)
    with pytest.raises(llm.MissingKeyError, match="OPENAI_API_KEY fehlt") as cabinet_error:
        cabinet_vision.detect_components(Path("nirgends.png"))
    assert cabinet_error.value.key == "OPENAI_API_KEY"


class _FakeVisionModel:
    """Steht fuer das Chatmodell des Providers: feste Antwort, kein Netz, keine Kosten."""

    def __init__(self, model: str, **kwargs):
        self.model, self.kwargs = model, kwargs

    def invoke(self, _messages, _config=None):
        item = '{"tag": "-K1", "kind": "Schuetz", "label": "Hauptschuetz", "x": 0.1, "y": 0.2, "w": 0.1, "h": 0.1}'
        return SimpleNamespace(content=f'{{"items": [{item}]}}')


def test_vision_startet_mit_nur_openai_api_key(monkeypatch, tmp_path):
    """Issue #50: Vision mit openai:gpt-* braucht nur OPENAI_API_KEY; der Provider ist gemockt."""
    from PIL import Image

    from app import llm
    from app.config import Settings
    from app.ingestion import cabinet_vision

    settings = Settings(
        _env_file=None,
        vision_model="openai:gpt-5",
        anthropic_api_key=None,
        openai_api_key="sk-openai",
    )
    created: list[_FakeVisionModel] = []

    def fake_init(model: str, **kwargs):
        created.append(_FakeVisionModel(model, **kwargs))
        return created[-1]

    monkeypatch.setattr(cabinet_vision, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "init_chat_model", fake_init)
    image = tmp_path / "schrank.png"
    Image.new("RGB", (80, 60), "white").save(image)

    items = cabinet_vision.detect_components(image)
    assert [item["tag"] for item in items] == ["-K1"]
    (model,) = created
    assert (model.model, model.kwargs["model_provider"], model.kwargs["api_key"]) == (
        "gpt-5",
        "openai",
        "sk-openai",
    )


def test_health_meldet_den_schluessel_des_chat_providers(monkeypatch):
    from app import main

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            chat_model="openai:gpt-5-mini", anthropic_api_key=None, openai_api_key="sk"
        ),
    )
    assert main.health() == {
        "status": "ok",
        "chat_model": "openai:gpt-5-mini",
        "api_key_configured": True,
    }
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            chat_model="claude-sonnet-5", anthropic_api_key=None, openai_api_key="sk"
        ),
    )
    assert main.health()["api_key_configured"] is False
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(chat_model="llama-3", anthropic_api_key="a", openai_api_key="b"),
    )
    assert (
        main.health()["api_key_configured"] is False
    )  # unbekannter Provider: kein 500 im Health-Check


def test_scl_ist_als_sps_quelle_zugelassen():
    from app.api.sources import ALLOWED_SUFFIXES
    from app.ingestion.doctype import detect, filename_doc_type
    from app.models import DocType

    assert ".scl" in ALLOWED_SUFFIXES
    detection = detect(FIXTURE.name, FIXTURE)
    assert detection.doc_type == DocType.PLC_PROGRAM and detection.source == "content"
    assert filename_doc_type("Steuerung_FB10.scl") == DocType.PLC_PROGRAM


def test_scl_liefert_bausteine_als_chunks():
    from app.ingestion.pipeline import _build_pieces

    pieces, page_count, note = _build_pieces("doc", FIXTURE, "plc_program", vision=False)
    assert page_count is None and note == ""
    labels = [p.meta.get("block", "") for p in pieces]
    assert any("FB_FOERDERBAND" in label.upper() for label in labels) and any(
        "MAIN" in label.upper() for label in labels
    )
    assert any(
        "K1_Vorwaerts := TRUE" in p.content for p in pieces
    )  # SCL-Rumpf bleibt im Baustein-Chunk
    assert all(p.kind == "awl_block" for p in pieces)
    # ohne Typangabe entscheidet die Endung
    by_suffix, _, _ = _build_pieces("doc", FIXTURE, "other", vision=False)
    assert [p.kind for p in by_suffix] == [p.kind for p in pieces]
