"""Langfuse-Konfiguration: ohne Schluessel ein No-op, mit Schluesseln Callback, Session und Tags.

Die Tests bauen nie eine Verbindung auf; sie pruefen nur, was an LangChain uebergeben wird.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import tracing
from app.ingestion import cabinet_vision, layout_vision, vision


def _settings(public: str | None = None, secret: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        langfuse_public_key=public,
        langfuse_secret_key=secret,
        langfuse_host="https://langfuse.invalid",
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    tracing.tracing_enabled.cache_clear()
    yield
    tracing.tracing_enabled.cache_clear()


def test_ohne_schluessel_leere_konfiguration(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _settings())
    assert tracing.tracing_enabled() is False
    assert tracing.trace_config("c1", ["eval:heute"], "claude-sonnet-5") == {}


def test_fehlendes_paket_schaltet_tracing_ab(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _settings("pk-lf-test", "sk-lf-test"))
    monkeypatch.setitem(sys.modules, "langfuse", None)  # import langfuse -> ImportError
    assert tracing.tracing_enabled() is False
    assert tracing.trace_config("c1", [], "claude-sonnet-5") == {}


def test_mit_schluesseln_callback_session_und_tags(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _settings("pk-lf-test", "sk-lf-test"))
    monkeypatch.setattr(tracing, "_handler", lambda: "HANDLER")
    config = tracing.trace_config("gespraech-7", ["eval:2026-09-27", "q:fb01-e03"], "claude-sonnet-5")
    assert config["callbacks"] == ["HANDLER"]
    assert config["metadata"]["langfuse_session_id"] == "gespraech-7"
    tags = config["metadata"]["langfuse_tags"]
    assert tags[:2] == ["stromlauf-ai", "model:claude-sonnet-5"]
    assert "eval:2026-09-27" in tags and "q:fb01-e03" in tags


def test_schluessel_landen_in_der_umgebung_fuer_den_handler(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setattr(tracing, "get_settings", lambda: _settings("pk-lf-test", "sk-lf-test"))
    monkeypatch.setattr(tracing, "_handler", lambda: "HANDLER")
    tracing.trace_config("c1", [], "m")
    import os

    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-lf-test"
    assert os.environ["LANGFUSE_HOST"] == "https://langfuse.invalid"


def _vision_settings() -> SimpleNamespace:
    return SimpleNamespace(
        vision_model="claude-sonnet-5",
        anthropic_api_key="sk-test",
        vision_max_edge=2400,
    )


class _FakeLLM:
    """Ersetzt ChatAnthropic: merkt sich die Konfiguration des Aufrufs."""

    last_config: object = "nicht aufgerufen"

    def __init__(self, **kwargs):
        pass

    def invoke(self, messages, config=None):
        type(self).last_config = config
        return SimpleNamespace(content='{"width_mm": 0, "depth_mm": 0, "items": []}')


def test_describe_page_gibt_die_trace_konfiguration_weiter(monkeypatch):
    monkeypatch.setattr(vision, "get_settings", _vision_settings)
    monkeypatch.setattr(vision, "ChatAnthropic", _FakeLLM)
    monkeypatch.setattr(vision, "render_page_png", lambda path, page: b"png")
    vision.describe_page(Path("plan.pdf"), 1, "", trace={"callbacks": ["H"]})
    assert _FakeLLM.last_config == {"callbacks": ["H"]}


def test_describe_page_ohne_trace_uebergibt_nichts(monkeypatch):
    monkeypatch.setattr(vision, "get_settings", _vision_settings)
    monkeypatch.setattr(vision, "ChatAnthropic", _FakeLLM)
    monkeypatch.setattr(vision, "render_page_png", lambda path, page: b"png")
    vision.describe_page(Path("plan.pdf"), 1)
    assert _FakeLLM.last_config is None


def test_detect_layout_gibt_die_trace_konfiguration_weiter(monkeypatch):
    monkeypatch.setattr(layout_vision, "get_settings", _vision_settings)
    monkeypatch.setattr(layout_vision, "ChatAnthropic", _FakeLLM)
    layout_vision.detect_layout(b"png", ["-M1"], trace={"callbacks": ["H"]})
    assert _FakeLLM.last_config == {"callbacks": ["H"]}


def test_detect_components_gibt_die_trace_konfiguration_weiter(monkeypatch):
    monkeypatch.setattr(cabinet_vision, "get_settings", _vision_settings)
    monkeypatch.setattr(cabinet_vision, "ChatAnthropic", _FakeLLM)
    monkeypatch.setattr(cabinet_vision, "load_png", lambda path: (b"png", 100, 80))
    cabinet_vision.detect_components(Path("schrank.png"), ["-K1"], trace={"callbacks": ["H"]})
    assert _FakeLLM.last_config == {"callbacks": ["H"]}


def test_vision_trace_setzt_modell_und_bereich_als_tags(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: SimpleNamespace(
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host="https://langfuse.invalid",
        vision_model="claude-sonnet-5",
    ))
    monkeypatch.setattr(tracing, "_handler", lambda: "HANDLER")
    config = tracing.vision_trace("dok-3", "seitenanalyse")
    assert config["metadata"]["langfuse_session_id"] == "dok-3"
    assert config["metadata"]["langfuse_tags"] == [
        "stromlauf-ai", "model:claude-sonnet-5", "ingestion", "seitenanalyse",
    ]
