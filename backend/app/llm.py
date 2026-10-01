"""Modellwahl je Provider: aus "openai:gpt-5-mini", "claude-sonnet-5" oder "ollama:qwen3.5:4b" wird ein
LangChain-Chatmodell.

Provider: anthropic (Standard, Namen mit "claude"), openai (Namen mit "gpt-", "o1", "o3", "o4") und ollama (lokal,
ueber Ollamas OpenAI-Endpunkt, ohne Schluessel und ohne Kosten). Der Schluessel kommt aus ANTHROPIC_API_KEY bzw.
OPENAI_API_KEY (app/config.py). Ein Aufwand hinter "@" ("openai:gpt-5.4-mini@none") wird zu reasoning_effort; bei
Ollama ist er ohne Angabe "none", damit kein Thinking laeuft. Die Ablauf-Extraktion (app/flow) nutzt weiter das
Anthropic-SDK direkt (strukturierte Ausgabe) und laeuft nicht ueber dieses Modul.
"""

from __future__ import annotations

import base64

from langchain.chat_models import init_chat_model

from app.config import get_settings

PROVIDER_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
LOCAL_PROVIDERS = ("ollama",)  # OpenAI-kompatibel, Basis-URL aus den Settings, kein Schluessel
PROVIDERS = (*PROVIDER_ENV, *LOCAL_PROVIDERS)
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")
_REASONING_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
# Platzhalter fuer lokale OpenAI-kompatible Endpunkte ohne Schluessel (Ollama prueft ihn nicht)
LOCAL_API_KEY = "lokal"


class MissingKeyError(RuntimeError):
    """Der Schluessel des Providers fehlt. Das ist Konfiguration, kein Fehler des Providers: Die API antwortet
    darauf mit 400 und nennt den Namen der Variable (Issue #50)."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key} fehlt{detail}")
        self.key = key


def split_effort(name: str) -> tuple[str, str | None]:
    """ "openai:gpt-5.4-mini@none" -> ("openai:gpt-5.4-mini", "none"); ohne "@" bleibt der Aufwand offen."""
    base, sep, effort = (name or "").strip().rpartition("@")
    if not sep:
        return name, None
    if effort not in EFFORTS:
        raise ValueError(f"Aufwand {effort!r} unbekannt; erlaubt: {', '.join(EFFORTS)}")
    return base, effort


def split_model(name: str) -> tuple[str, str]:
    """ "provider:modell" oder ein Name, an dem der Provider erkennbar ist -> (provider, modell)."""
    name, _effort = split_effort(name)
    name = (name or "").strip()
    if not name:
        raise ValueError("Kein Modellname angegeben")
    if ":" in name:
        provider, model = name.split(":", 1)
        provider = provider.strip().lower()
        if provider not in PROVIDERS:
            raise ValueError(f"Provider {provider!r} unbekannt; erlaubt: {', '.join(PROVIDERS)}")
        if not model.strip():
            raise ValueError(f"Kein Modell hinter {provider}:")
        return provider, model.strip()
    if name.startswith("claude"):
        return "anthropic", name
    if name.startswith(_OPENAI_PREFIXES):
        return "openai", name
    raise ValueError(
        f"Modell {name!r} ohne erkennbaren Provider; schreib openai:<modell>, anthropic:<modell> oder ollama:<modell>"
    )


def api_key_for(provider: str, settings=None) -> str | None:
    settings = settings or get_settings()
    attribute = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}[provider]
    return getattr(settings, attribute, None)


def missing_key(name: str, settings=None) -> str | None:
    """Name der fehlenden Umgebungsvariable fuer das Modell (ANTHROPIC_API_KEY, OPENAI_API_KEY), sonst None.

    Lokale Provider brauchen keinen Schluessel. ValueError bei einem Modellnamen ohne erkennbaren Provider.
    """
    provider, _ = split_model(name)
    if provider in LOCAL_PROVIDERS:
        return None
    return None if api_key_for(provider, settings) else PROVIDER_ENV[provider]


def is_reasoning_model(name: str) -> bool:
    """OpenAI-Modell, das vor der Antwort nachdenkt (gpt-5*, gpt-6*, o1/o3/o4, nicht gpt-5-chat): Die Denk-Tokens
    zaehlen als Ausgabe und gegen max_tokens."""
    try:
        provider, model = split_model(name)
    except ValueError:
        return False
    model = model.lower()
    return provider == "openai" and model.startswith(_REASONING_PREFIXES) and "chat" not in model


def make_chat_model(
    name: str,
    *,
    max_tokens: int,
    max_retries: int = 3,
    streaming: bool = False,
    timeout: float | None = None,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
):
    """Chatmodell fuer den Namen; bricht laut ab, wenn der Schluessel des Providers fehlt.

    base_url: OpenAI-kompatibler Endpunkt fuer "openai:<modell>", etwa Ollama unter http://localhost:11434/v1.
    Der Schluessel des Anbieters geht nie an eine fremde Basis-URL; das OpenAI-SDK verlangt trotzdem einen
    und bekommt LOCAL_API_KEY. "ollama:<modell>" nimmt OLLAMA_BASE_URL aus den Settings. Ein Endpunkt mit eigenem
    Schluessel wird damit (noch) nicht unterstuetzt.
    reasoning_effort: "none" | "minimal" | "low" | "medium" | "high" fuer OpenAI-Reasoning-Modelle (is_reasoning_model)
    und Ollama (dort schaltet "none" das Thinking ab, Standard ohne Angabe); Feld `reasoning_effort` von ChatOpenAI.
    Andere Modelle lehnen den Parameter ab. Steht der Aufwand schon im Namen ("@none"), darf er hier nicht nochmal
    stehen. GPT-6 mit Werkzeugen leitet langchain-openai von selbst ueber die Responses-API.
    """
    name, named_effort = split_effort(name)
    if named_effort and reasoning_effort:
        raise ValueError(
            f"Aufwand doppelt: {named_effort!r} im Namen und {reasoning_effort!r} als Parameter"
        )
    reasoning_effort = reasoning_effort or named_effort
    provider, model = split_model(name)
    local = provider in LOCAL_PROVIDERS
    if local:
        base_url = base_url or get_settings().ollama_base_url
        reasoning_effort = reasoning_effort or "none"
    if base_url and provider != "openai" and not local:
        raise ValueError(
            f"Basis-URL nur fuer OpenAI-kompatible Endpunkte; schreib openai:<modell> statt {name!r}"
        )
    if reasoning_effort and not (local or is_reasoning_model(name)):
        raise ValueError(
            f"reasoning_effort nur fuer OpenAI-Reasoning-Modelle oder Ollama, nicht fuer {name!r}"
        )
    key = LOCAL_API_KEY if base_url else api_key_for(provider)
    if not key:
        raise MissingKeyError(
            PROVIDER_ENV[provider],
            f" fuer Modell {name!r}. In .env eintragen und Backend neu starten.",
        )
    kwargs = {
        "model_provider": "openai" if local else provider,
        "api_key": key,
        "max_tokens": max_tokens,
        "max_retries": max_retries,
        "streaming": streaming,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    if timeout is not None:
        kwargs["timeout"] = timeout
    return init_chat_model(model, **kwargs)


def image_block(png: bytes, mime_type: str = "image/png") -> dict:
    """Standard-Inhaltsblock fuer Bilder (LangChain v1), den Anthropic und OpenAI gleichermassen annehmen."""
    return {
        "type": "image",
        "base64": base64.standard_b64encode(png).decode("ascii"),
        "mime_type": mime_type,
    }
