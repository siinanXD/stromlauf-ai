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
    assert (
        llm.make_chat_model("openai:gpt-5-mini", max_tokens=4000, max_retries=2, streaming=True)
        == "LLM"
    )
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
    assert block == {
        "type": "image",
        "base64": base64.standard_b64encode(b"\x89PNG").decode("ascii"),
        "mime_type": "image/png",
    }
    assert llm.image_block(b"x", "image/jpeg")["mime_type"] == "image/jpeg"


def test_make_chat_model_reicht_die_basis_url_durch_und_braucht_dann_keinen_schluessel(monkeypatch):
    """Planleser mit lokalem Endpunkt (Ollama): Basis-URL an ChatOpenAI, der Anbieter-Schluessel bleibt daheim."""
    seen = {}

    def fake_init(model, **kwargs):
        seen.clear()
        seen.update(kwargs, model=model)
        return "LLM"

    monkeypatch.setattr(llm, "init_chat_model", fake_init)
    monkeypatch.setattr(llm, "get_settings", lambda: _settings(openai_api_key=None))
    assert (
        llm.make_chat_model(
            "openai:qwen3.5:4b", max_tokens=100, base_url="http://localhost:11434/v1"
        )
        == "LLM"
    )
    assert seen["model"] == "qwen3.5:4b" and seen["model_provider"] == "openai"
    assert seen["base_url"] == "http://localhost:11434/v1" and seen["api_key"] == llm.LOCAL_API_KEY

    monkeypatch.setattr(llm, "get_settings", lambda: _settings())
    llm.make_chat_model("openai:gpt-5-mini", max_tokens=100, base_url="http://localhost:11434/v1")
    assert seen["api_key"] == llm.LOCAL_API_KEY  # o-key geht nie an eine fremde Basis-URL
    llm.make_chat_model("openai:gpt-5-mini", max_tokens=100)
    assert "base_url" not in seen and seen["api_key"] == "o-key"


def test_basis_url_gilt_nur_fuer_openai_kompatible_endpunkte(monkeypatch):
    monkeypatch.setattr(llm, "init_chat_model", lambda *a, **k: "LLM")
    monkeypatch.setattr(llm, "get_settings", lambda: _settings())
    with pytest.raises(ValueError, match="openai:"):
        llm.make_chat_model("claude-sonnet-5", max_tokens=100, base_url="http://localhost:11434/v1")
    monkeypatch.setattr(llm, "get_settings", lambda: _settings(openai_api_key=None))
    with pytest.raises(llm.MissingKeyError, match="OPENAI_API_KEY"):
        llm.make_chat_model("openai:gpt-5-mini", max_tokens=100, base_url="")


def test_reasoning_modelle_erkennt_llm_am_namen():
    assert llm.is_reasoning_model("openai:gpt-5-mini") and llm.is_reasoning_model("gpt-5")
    assert llm.is_reasoning_model("o3-mini") and llm.is_reasoning_model("openai:o4-mini")
    assert not llm.is_reasoning_model("openai:gpt-5-chat-latest")
    assert not llm.is_reasoning_model("openai:gpt-4.1-mini")
    assert not llm.is_reasoning_model("claude-sonnet-5")
    assert not llm.is_reasoning_model("openai:qwen3.5:4b") and not llm.is_reasoning_model("llama")


def test_reasoning_effort_geht_als_feld_von_chatopenai_durch(monkeypatch):
    """langchain-openai 1.6: ChatOpenAI.reasoning_effort ("minimal" | "low" | "medium" | "high")."""
    seen = {}
    monkeypatch.setattr(
        llm, "init_chat_model", lambda model, **kwargs: seen.update(kwargs) or "LLM"
    )
    monkeypatch.setattr(llm, "get_settings", lambda: _settings())
    llm.make_chat_model("openai:gpt-5-mini", max_tokens=100, reasoning_effort="low")
    assert seen["reasoning_effort"] == "low"
    seen.clear()
    llm.make_chat_model("openai:gpt-5-mini", max_tokens=100)
    assert "reasoning_effort" not in seen
    with pytest.raises(ValueError, match="Reasoning"):
        llm.make_chat_model("openai:gpt-4.1-mini", max_tokens=100, reasoning_effort="low")


def test_ollama_ist_ein_provider_ohne_schluessel_mit_lokaler_basis_url(monkeypatch):
    """ollama:<modell> spricht Ollamas OpenAI-Endpunkt an; Thinking ist aus, solange kein Aufwand angegeben ist."""
    seen = {}
    monkeypatch.setattr(
        llm, "init_chat_model", lambda model, **kwargs: seen.update(kwargs, model=model) or "LLM"
    )
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: _settings(openai_api_key=None, ollama_base_url="http://localhost:11434/v1"),
    )
    assert llm.split_model("ollama:qwen3.5:4b") == ("ollama", "qwen3.5:4b")
    assert llm.missing_key("ollama:qwen3.5:4b") is None
    assert llm.make_chat_model("ollama:qwen3.5:4b", max_tokens=100) == "LLM"
    assert seen["model"] == "qwen3.5:4b" and seen["model_provider"] == "openai"
    assert seen["base_url"] == "http://localhost:11434/v1" and seen["api_key"] == llm.LOCAL_API_KEY
    assert seen["reasoning_effort"] == "none"
    seen.clear()
    llm.make_chat_model("ollama:qwen3.5:9b", max_tokens=100, reasoning_effort="low")
    assert seen["reasoning_effort"] == "low"


def test_aufwand_steht_hinter_dem_at_im_modellnamen():
    """Eval und CHAT_MODEL nennen den Aufwand im Namen: openai:gpt-5.4-mini@none."""
    assert llm.split_effort("openai:gpt-5.4-mini@none") == ("openai:gpt-5.4-mini", "none")
    assert llm.split_effort("ollama:qwen3.5:4b@low") == ("ollama:qwen3.5:4b", "low")
    assert llm.split_effort("claude-sonnet-5") == ("claude-sonnet-5", None)
    with pytest.raises(ValueError, match="Aufwand"):
        llm.split_effort("openai:gpt-5.4-mini@turbo")


def test_make_chat_model_nimmt_den_aufwand_aus_dem_namen(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        llm, "init_chat_model", lambda model, **kwargs: seen.update(kwargs, model=model) or "LLM"
    )
    monkeypatch.setattr(llm, "get_settings", lambda: _settings())
    llm.make_chat_model("openai:gpt-5.4-mini@none", max_tokens=100)
    assert seen["model"] == "gpt-5.4-mini" and seen["reasoning_effort"] == "none"
    with pytest.raises(ValueError, match="Aufwand"):
        llm.make_chat_model("openai:gpt-5.4-mini@none", max_tokens=100, reasoning_effort="low")


def test_gpt6_zaehlt_als_reasoning_modell():
    assert llm.is_reasoning_model("openai:gpt-6-sol") and llm.is_reasoning_model("gpt-5.6-terra")
    assert llm.is_reasoning_model("openai:gpt-6-astra@low")
    assert not llm.is_reasoning_model("ollama:qwen3.5:4b")


def test_chatopenai_leitet_gpt6_mit_werkzeugen_ueber_die_responses_api():
    """GPT-6 Astra und GPT-6.1 Sol rufen Werkzeuge nur ueber die Responses-API; langchain-openai 1.6 entscheidet das
    am Namen, sobald tools dabei sind. Nur Aufbau, keine Anfrage."""
    from langchain_openai import ChatOpenAI

    tools = [{"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}]
    assert ChatOpenAI(model="gpt-6-astra", api_key="x", max_tokens=100)._use_responses_api(
        {"tools": tools}
    )
    assert ChatOpenAI(model="gpt-6.1-sol", api_key="x", max_tokens=100)._use_responses_api(
        {"tools": tools}
    )
    assert not ChatOpenAI(model="gpt-5.4-mini", api_key="x", max_tokens=100)._use_responses_api(
        {"tools": tools}
    )


def test_chatopenai_kennt_das_feld_reasoning_effort():
    """Nur Aufbau mit Platzhalter-Schluessel, keine Anfrage: das Feld gibt es in der installierten Version."""
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model="gpt-5-mini", api_key="x", reasoning_effort="low", max_tokens=100)
    assert model.reasoning_effort == "low"
    assert model._default_params["reasoning_effort"] == "low"
