"""Modellwahl je Provider: aus "openai:gpt-5-mini" oder "claude-sonnet-5" wird ein LangChain-Chatmodell.

Provider heute: anthropic (Standard, Namen mit "claude") und openai (Namen mit "gpt-", "o1", "o3", "o4").
Der Schluessel kommt aus ANTHROPIC_API_KEY bzw. OPENAI_API_KEY (app/config.py). Die Ablauf-Extraktion
(app/flow) nutzt weiter das Anthropic-SDK direkt (strukturierte Ausgabe) und laeuft nicht ueber dieses Modul.
"""

from __future__ import annotations

import base64

from langchain.chat_models import init_chat_model

from app.config import get_settings

PROVIDER_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")


def split_model(name: str) -> tuple[str, str]:
    """"provider:modell" oder ein Name, an dem der Provider erkennbar ist -> (provider, modell)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Kein Modellname angegeben")
    if ":" in name:
        provider, model = name.split(":", 1)
        provider = provider.strip().lower()
        if provider not in PROVIDER_ENV:
            raise ValueError(f"Provider {provider!r} unbekannt; erlaubt: {', '.join(PROVIDER_ENV)}")
        if not model.strip():
            raise ValueError(f"Kein Modell hinter {provider}:")
        return provider, model.strip()
    if name.startswith("claude"):
        return "anthropic", name
    if name.startswith(_OPENAI_PREFIXES):
        return "openai", name
    raise ValueError(f"Modell {name!r} ohne erkennbaren Provider; schreib openai:<modell> oder anthropic:<modell>")


def api_key_for(provider: str, settings=None) -> str | None:
    settings = settings or get_settings()
    return {"anthropic": settings.anthropic_api_key, "openai": settings.openai_api_key}[provider]


def make_chat_model(
    name: str,
    *,
    max_tokens: int,
    max_retries: int = 3,
    streaming: bool = False,
    timeout: float | None = None,
):
    """Chatmodell fuer den Namen; bricht laut ab, wenn der Schluessel des Providers fehlt."""
    provider, model = split_model(name)
    key = api_key_for(provider)
    if not key:
        raise RuntimeError(f"{PROVIDER_ENV[provider]} fehlt fuer Modell {name!r}. In .env eintragen und Backend neu starten.")
    kwargs = {"model_provider": provider, "api_key": key, "max_tokens": max_tokens, "max_retries": max_retries, "streaming": streaming}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return init_chat_model(model, **kwargs)


def image_block(png: bytes, mime_type: str = "image/png") -> dict:
    """Standard-Inhaltsblock fuer Bilder (LangChain v1), den Anthropic und OpenAI gleichermassen annehmen."""
    return {"type": "image", "base64": base64.standard_b64encode(png).decode("ascii"), "mime_type": mime_type}
