"""Modell je Chat-Anfrage (Evals vergleichen Provider): Anfragefeld, Pruefung, Weitergabe an den Agenten."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.agent import graph
from app.api import chat
from app.schemas import ChatRequest


def test_chat_request_hat_optionales_modell():
    assert ChatRequest(message="hi").model is None
    assert ChatRequest(message="hi", model="openai:gpt-5-mini").model == "openai:gpt-5-mini"


def test_effective_model_nimmt_die_einstellung_ohne_wunsch(monkeypatch):
    monkeypatch.setattr(chat, "get_settings", lambda: SimpleNamespace(chat_model="claude-sonnet-5", anthropic_api_key="a", openai_api_key=None))
    assert chat.effective_model(None) == "claude-sonnet-5"
    assert chat.effective_model("claude-opus-5") == "claude-opus-5"


def test_effective_model_lehnt_unbekannte_modelle_und_fehlende_schluessel_mit_400_ab(monkeypatch):
    monkeypatch.setattr(chat, "get_settings", lambda: SimpleNamespace(chat_model="claude-sonnet-5", anthropic_api_key="a", openai_api_key=None))
    with pytest.raises(HTTPException) as unknown:
        chat.effective_model("llama-3")
    assert unknown.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        chat.effective_model("openai:gpt-5-mini")
    assert missing.value.status_code == 400
    assert "OPENAI_API_KEY" in missing.value.detail


def test_thread_config_traegt_das_modell():
    config = chat._thread_config("conv-1", ["s1"], model="openai:gpt-5-mini")
    assert config["configurable"]["model"] == "openai:gpt-5-mini"


def test_agent_nimmt_modell_aus_der_konfiguration_sonst_einstellung(monkeypatch):
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(chat_model="claude-sonnet-5"))
    assert graph.model_name_for({"configurable": {"model": "openai:gpt-5-mini"}}) == "openai:gpt-5-mini"
    assert graph.model_name_for({"configurable": {}}) == "claude-sonnet-5"
    assert graph.model_name_for(None) == "claude-sonnet-5"
