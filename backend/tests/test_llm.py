"""Modellwahl je Provider (app/llm.py): Namen aufloesen, Schluessel pruefen, Bildbloecke providerneutral."""

import base64
from types import SimpleNamespace

import pytest

from app import llm


def _settings(**overrides):
    base = dict(anthropic_api_key="a-key", openai_api_key="o-key", chat_model="claude-sonnet-5")
    base.update(overrides)
    return SimpleNamespace(**base)


def test_split_model_nimmt_prefix_oder_erkennt_den_provider_am_namen():
    assert llm.split_model("openai:gpt-5-mini") == ("openai", "gpt-5-mini")
    assert llm.split_model("anthropic:claude-sonnet-5") == ("anthropic", "claude-sonnet-5")
    assert llm.split_model("claude-opus-5") == ("anthropic", "claude-opus-5")
    assert llm.split_model("gpt-4.1-mini") == ("openai", "gpt-4.1-mini")
    assert llm.split_model("o3-mini") == ("openai", "o3-mini")


def test_split_model_lehnt_unbekannte_provider_und_namen_ab():
    with pytest.raises(ValueError, match="mistral"):
        llm.split_model("mistral:large")
    with pytest.raises(ValueError, match="openai:"):
        llm.split_model("llama-3")
    with pytest.raises(ValueError):
        llm.split_model("")


def test_api_key_for_liest_den_schluessel_des_providers(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: _settings(openai_api_key=None))
    assert llm.api_key_for("anthropic") == "a-key"
    assert llm.api_key_for("openai") is None


def test_make_chat_model_ruft_init_chat_model_mit_provider_und_schluessel(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: _settings())
    seen = {}

    def fake_init(model, **kwargs):
        seen["model"] = model
        seen.update(kwargs)
        return "LLM"

    monkeypatch.setattr(llm, "init_chat_model", fake_init)
    assert llm.make_chat_model("openai:gpt-5-mini", max_tokens=4000, max_retries=2, streaming=True) == "LLM"
    assert seen["model"] == "gpt-5-mini"
    assert seen["model_provider"] == "openai"
    assert seen["api_key"] == "o-key"
    assert seen["max_tokens"] == 4000 and seen["max_retries"] == 2 and seen["streaming"] is True


def test_make_chat_model_nennt_fehlenden_schluessel_beim_namen(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: _settings(openai_api_key=None))
    monkeypatch.setattr(llm, "init_chat_model", lambda *a, **k: "LLM")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm.make_chat_model("openai:gpt-5-mini", max_tokens=100)
    assert llm.make_chat_model("claude-sonnet-5", max_tokens=100) == "LLM"


def test_image_block_ist_ein_standard_inhaltsblock():
    block = llm.image_block(b"\x89PNG")
    assert block == {"type": "image", "base64": base64.standard_b64encode(b"\x89PNG").decode("ascii"), "mime_type": "image/png"}
    assert llm.image_block(b"x", "image/jpeg")["mime_type"] == "image/jpeg"
