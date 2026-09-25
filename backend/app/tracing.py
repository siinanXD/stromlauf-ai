"""Langfuse-Tracing, optional. Ohne Keys in .env passiert nichts.

Jeder Chat-Lauf wird ein Trace mit allen Modell- und Tool-Aufrufen, Tokens und Kosten.
Der Eval-Runner haengt Tags an (eval:<lauf>, q:<frage>) und schreibt seine Scores dazu.
"""

import logging
import os

from app.config import get_settings

logger = logging.getLogger(__name__)
_available: bool | None = None


def tracing_enabled() -> bool:
    global _available
    if _available is not None:
        return _available
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        _available = False
        return False
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    try:
        import langfuse  # noqa: F401
    except ImportError:
        logger.warning("LANGFUSE_* gesetzt, aber Paket fehlt: pip install -e \".[tracing]\"")
        _available = False
        return False
    _available = True
    logger.info("Langfuse-Tracing aktiv (%s)", settings.langfuse_host)
    return True


def trace_config(conversation_id: str, tags: list[str], model: str) -> dict:
    """Callbacks und Metadaten fuer graph.astream(config=...). Leer, wenn Tracing aus ist."""
    if not tracing_enabled():
        return {}
    from langfuse.langchain import CallbackHandler

    return {
        "callbacks": [CallbackHandler()],
        "metadata": {
            "langfuse_session_id": conversation_id,
            "langfuse_tags": ["stromlauf-ai", f"model:{model}", *tags],
        },
    }
