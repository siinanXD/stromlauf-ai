"""Preistabelle (app/pricing.py): beide Provider, datierte IDs, laengster Praefix gewinnt."""

from app.pricing import cost_usd, prices_for


def test_openai_und_anthropic_preise_sind_hinterlegt():
    assert prices_for("gpt-5-mini") == (0.25, 2.0)
    assert prices_for("gpt-5") == (1.25, 10.0)
    assert prices_for("gpt-5-nano") == (0.05, 0.40)
    assert prices_for("gpt-4.1-mini") == (0.40, 1.60)
    assert prices_for("text-embedding-3-small") == (0.02, 0.0)
    assert prices_for("claude-sonnet-5") == (2.0, 10.0)


def test_datierte_ids_nehmen_den_laengsten_passenden_praefix():
    assert prices_for("gpt-5-mini-2026-03-01") == (0.25, 2.0)  # nicht der Preis von gpt-5
    assert prices_for("gpt-5-2026-03-01") == (1.25, 10.0)
    assert prices_for("claude-sonnet-5-20260115") == (2.0, 10.0)


def test_provider_praefix_wird_ignoriert():
    assert prices_for("openai:gpt-5-nano") == (0.05, 0.40)
    assert prices_for("anthropic:claude-opus-5") == (5.0, 25.0)
    assert prices_for("mistral:large") is None


def test_cost_usd_rechnet_je_million_tokens():
    assert cost_usd("gpt-5-mini", 1_000_000, 500_000) == 1.25
    assert cost_usd("unbekannt", 10, 10) == 0.0
