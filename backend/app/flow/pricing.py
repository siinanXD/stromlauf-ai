"""Preise je Modell (USD je 1M Token), fuer Kosten im JSON und im Log.

Eintrag: (Eingabe, Ausgabe) oder (Eingabe, Ausgabe, Cache-Treffer). Ohne dritten Wert kostet ein Cache-Treffer ein
Zehntel der Eingabe (Standard beider Provider). Unbekannte Modelle kosten 0 mit Warnung im Log; lokale Modelle
("ollama:") kosten 0 ohne Warnung. Langfuse rechnet zusaetzlich aus eigener Preistabelle.
"""

import logging

logger = logging.getLogger("flow")

Prices = tuple[float, float] | tuple[float, float, float]

PRICES_PER_MTOK: dict[str, Prices] = {
    # Anthropic (platform.claude.com/docs/en/about-claude/pricing, Stand 2026-10-02); Opus 5.5 liest aus dem Cache
    # mit 0,05-fach, alle anderen mit 0,1-fach
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    # OpenAI (developers.openai.com/api/docs/pricing, Stand 2026-10-02), Embeddings nur Eingabe.
    # Stufen: GPT-6 Astra > Sol > Luna; GPT-5.6 Sol = frueher ohne Suffix, Terra = mini, Luna = nano.
    "gpt-6-astra": (10.0, 50.0, 1.0),
    "gpt-6-sol": (2.0, 10.0, 0.20),
    "gpt-6.1-sol": (2.0, 10.0, 0.10),
    "gpt-6-luna": (0.10, 0.50, 0.01),
    "gpt-5.6-sol": (4.0, 20.0, 0.40),
    "gpt-5.6-terra": (2.0, 12.0, 0.20),
    "gpt-5.6-luna": (0.20, 1.20, 0.02),
    "gpt-5.5": (5.0, 30.0, 0.50),
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
LOCAL_PREFIX = "ollama:"
FREE: Prices = (0.0, 0.0, 0.0)

# Prompt-Cache: Treffer kosten ein Zehntel der Eingabe, wenn die Tabelle nichts anderes sagt; Anthropic schreibt
# (5 min) mit 1,25-fach, OpenAI meldet kein Schreiben
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25


def _bare(model: str) -> str:
    """ "openai:gpt-5-mini" -> "gpt-5-mini"; ohne Praefix unveraendert."""
    return model.split(":", 1)[1] if ":" in model else model


def prices_for(model: str) -> Prices | None:
    """Eintrag zum Modell; die API liefert datierte IDs (claude-sonnet-5-20260115, gpt-5-mini-2026-03-01).

    Bei datierten IDs gewinnt der laengste passende Eintrag, sonst wuerde gpt-5 den Preis von gpt-5-mini verdecken.
    """
    if model.startswith(LOCAL_PREFIX):
        return FREE
    model = _bare(model)
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    matches = [name for name in PRICES_PER_MTOK if model.startswith(name)]
    if not matches:
        return None
    return PRICES_PER_MTOK[max(matches, key=len)]


def cost_usd(
    model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_creation: int = 0
) -> float:
    """Kosten eines Aufrufs; input_tokens enthaelt die Cache-Tokens (so liefert es LangChain), die hier guenstiger
    bzw. teurer zaehlen als frische Eingabe."""
    prices = prices_for(model)
    if prices is None:
        logger.warning('{"event": "unknown_model_price", "model": "%s"}', model)
        return 0.0
    input_price, output_price = prices[0], prices[1]
    cached_price = prices[2] if len(prices) > 2 else input_price * CACHE_READ_FACTOR
    fresh = max(input_tokens - cache_read - cache_creation, 0)
    total = (
        fresh * input_price
        + cache_read * cached_price
        + cache_creation * input_price * CACHE_WRITE_FACTOR
        + output_tokens * output_price
    )
    return round(total / 1_000_000, 6)
