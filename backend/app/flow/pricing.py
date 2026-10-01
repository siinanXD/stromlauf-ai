"""Preise je Modell (USD je 1M Token, Stand 2026-06), fuer Kosten im JSON und im Log.

Unbekannte Modelle kosten 0 mit Warnung im Log; Langfuse rechnet zusaetzlich aus eigener Preistabelle.
"""

import logging

logger = logging.getLogger("flow")

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic (claude-api-Skill, 2026-06)
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    # OpenAI (developers.openai.com/api/docs/pricing, Stand 2026-09-28), Embeddings nur Eingabe
    "gpt-5": (1.25, 10.0),
    "gpt-5-mini": (0.25, 2.0),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5.1": (1.25, 10.0),
    "gpt-5.2": (1.75, 14.0),
    "gpt-5.4": (2.50, 15.0),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3": (2.0, 8.0),
    "o3-mini": (1.10, 4.40),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def _bare(model: str) -> str:
    """ "openai:gpt-5-mini" -> "gpt-5-mini"; ohne Praefix unveraendert."""
    return model.split(":", 1)[1] if ":" in model else model


def prices_for(model: str) -> tuple[float, float] | None:
    """Eintrag zum Modell; die API liefert datierte IDs (claude-sonnet-5-20260115, gpt-5-mini-2026-03-01).

    Bei datierten IDs gewinnt der laengste passende Eintrag, sonst wuerde gpt-5 den Preis von gpt-5-mini verdecken.
    """
    model = _bare(model)
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    matches = [name for name in PRICES_PER_MTOK if model.startswith(name)]
    if not matches:
        return None
    return PRICES_PER_MTOK[max(matches, key=len)]


# Prompt-Cache: Treffer kosten bei beiden Providern ein Zehntel der Eingabe, Anthropic schreibt (5 min) mit 1,25-fach
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25


def cost_usd(
    model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_creation: int = 0
) -> float:
    """Kosten eines Aufrufs; input_tokens enthaelt die Cache-Tokens (so liefert es LangChain), die hier guenstiger
    bzw. teurer zaehlen als frische Eingabe."""
    prices = prices_for(model)
    if prices is None:
        logger.warning('{"event": "unknown_model_price", "model": "%s"}', model)
        return 0.0
    fresh = max(input_tokens - cache_read - cache_creation, 0)
    weighted_input = fresh + cache_read * CACHE_READ_FACTOR + cache_creation * CACHE_WRITE_FACTOR
    return round((weighted_input * prices[0] + output_tokens * prices[1]) / 1_000_000, 6)
