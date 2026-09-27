"""Langfuse-Tracing, optional. Ohne Schluessel in der .env passiert nichts.

Ein Chat-Lauf wird ein Trace mit allen Modell- und Werkzeugaufrufen, Tokens und Kosten. Die
Vision-Aufrufe (Seitenanalyse, Draufsicht, Schaltschrank) haengen mit derselben Konfiguration
am Trace ihres Dokuments bzw. Bildes, damit die teuren Aufrufe zuordenbar sind. Der
Eval-Runner haengt Tags an (`eval:<lauf>`, `q:<frage>`) und schreibt seine Scores dazu.

Die Ablauf-Extraktion instrumentiert sich selbst (`app/flow/tracing.py`, eigene Spans und
Kosten je Modellaufruf) und nutzt von hier nur `tracing_enabled`.
"""

import logging
import os
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def tracing_enabled() -> bool:
    """Schluessel gesetzt und Paket vorhanden? Ergebnis wird gemerkt (cache_clear in Tests)."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return False
    try:
        import langfuse  # noqa: F401
    except ImportError:
        logger.warning('LANGFUSE_* gesetzt, aber Paket fehlt: pip install -e "backend[trace]"')
        return False
    logger.info("Langfuse-Tracing aktiv (%s)", settings.langfuse_host)
    return True


def _export_keys() -> None:
    """Der CallbackHandler liest seine Zugangsdaten aus der Umgebung, nicht aus den Settings."""
    settings = get_settings()
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key or "")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key or "")
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


def _handler():
    """Eigene Funktion, damit Tests den Handler ersetzen koennen, ohne Langfuse zu laden."""
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def langfuse_client():
    """Client fuer alles, was nicht ueber LangChain laeuft (Extraktion, Scores aus dem Eval).

    None, wenn Tracing aus ist - der Aufrufer ueberspringt dann seinen Teil.
    """
    if not tracing_enabled():
        return None
    _export_keys()
    from langfuse import Langfuse

    return Langfuse()


def vision_trace(session_id: str, kind: str) -> dict:
    """Trace eines einzelnen Vision-Aufrufs (Seitenanalyse, Draufsicht, Schaltschrank)."""
    return trace_config(session_id, ["ingestion", kind], get_settings().vision_model)


def trace_config(session_id: str, tags: list[str], model: str) -> dict:
    """Konfiguration fuer `graph.astream(config=...)` oder `llm.invoke(messages, config)`.

    Leeres Dict, wenn Tracing aus ist; der Aufrufer gibt es dann unveraendert weiter.
    `session_id` gruppiert zusammengehoerige Laeufe in Langfuse (Konversation, Dokument, Bild).
    """
    if not tracing_enabled():
        return {}
    _export_keys()
    return {
        "callbacks": [_handler()],
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["stromlauf-ai", f"model:{model}", *tags],
        },
    }
