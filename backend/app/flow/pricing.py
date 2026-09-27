"""Preise je Modell (USD je 1M Token, Stand 2026-06), fuer Kosten im JSON und im Log.

Unbekannte Modelle kosten 0 mit Warnung im Log; Langfuse rechnet zusaetzlich aus eigener Preistabelle.
"""

import logging

logger = logging.getLogger("flow")

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
}


def prices_for(model: str) -> tuple[float, float] | None:
    """Eintrag zum Modell; die API liefert datierte IDs (claude-sonnet-5-20260115)."""
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    for name, prices in PRICES_PER_MTOK.items():
        if model.startswith(name):
            return prices
    return None


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = prices_for(model)
    if prices is None:
        logger.warning('{"event": "unknown_model_price", "model": "%s"}', model)
        return 0.0
    return round((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000, 6)
