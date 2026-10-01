"""Kostenbuch ohne Datenbank: Kostenrechnung, Token-Auslesen, Callback-Sammler, Schaetzung."""

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app import ledger


def test_microcents_aus_preistabelle():
    # sonnet-5: 2 USD / M in, 10 USD / M out -> 1000 in + 100 out = 0.003 USD = 0.3 Cent
    assert ledger.microcents("claude-sonnet-5", 1000, 100) == 300_000
    assert ledger.microcents("unbekanntes-modell", 1000, 100) == 0


def test_usage_of_liest_usage_metadata_und_modell():
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
        response_metadata={"model_name": "claude-sonnet-5-20260115"},
    )
    usage = ledger.usage_of(message, "fallback")
    assert usage == ledger.Usage("claude-sonnet-5-20260115", 12, 3)
    assert ledger.usage_of(AIMessage(content="ohne"), "fallback") is None
    assert ledger.usage_of(None, "fallback") is None


def test_collect_sammelt_tokens_jedes_aufrufs_ohne_signaturaenderung():
    llm = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="a",
                usage_metadata={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
            ),
            AIMessage(
                content="b",
                usage_metadata={"input_tokens": 20, "output_tokens": 2, "total_tokens": 22},
            ),
        ]
    )
    original = {"metadata": {"langfuse_session_id": "x"}}
    config, collector = ledger.collect(original, model="claude-sonnet-5")
    assert "callbacks" not in original  # Original unveraendert
    llm.invoke([HumanMessage("1")], config)
    llm.invoke([HumanMessage("2")], config)
    assert [u.input_tokens for u in collector.calls] == [10, 20]
    assert collector.total() == ledger.Usage("claude-sonnet-5", 30, 3)
    assert ledger.collect(None)[1].total() is None


def test_usage_addition_behaelt_modell():
    total = ledger.Usage("m1", 1, 2) + ledger.Usage("m2", 3, 4)
    assert total == ledger.Usage("m1", 4, 6)


def test_usage_of_liest_cache_tokens_beider_provider():
    # LangChain: input_tokens enthaelt die Cache-Tokens; Anthropic meldet Lesen und Schreiben, OpenAI nur Lesen
    anthropic = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 5,
            "total_tokens": 1005,
            "input_token_details": {"cache_read": 700, "cache_creation": 200},
        },
    )
    assert ledger.usage_of(anthropic, "claude-sonnet-5") == ledger.Usage(
        "claude-sonnet-5", 1000, 5, 700, 200
    )
    openai = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 5,
            "total_tokens": 1005,
            "input_token_details": {"cache_read": 640},
        },
    )
    assert ledger.usage_of(openai, "openai:gpt-5-mini") == ledger.Usage(
        "openai:gpt-5-mini", 1000, 5, 640, 0
    )
    assert ledger.Usage("m", 1, 1, 1, 1) + ledger.Usage("m", 1, 1, 1, 1) == ledger.Usage(
        "m", 2, 2, 2, 2
    )


def test_microcents_rechnet_cache_lesen_mit_zehntel_und_schreiben_mit_fuenf_viertel():
    # sonnet-5: 2 USD / M in. 1000 Eingabe, davon 700 aus dem Cache (0,2 USD/M) und 200 neu geschrieben (2,5 USD/M)
    plain = ledger.microcents("claude-sonnet-5", 1000, 0)
    cached = ledger.microcents("claude-sonnet-5", 1000, 0, cache_read=700, cache_creation=200)
    expected_usd = (100 * 2.0 + 700 * 0.2 + 200 * 2.5) / 1_000_000
    assert cached == round(expected_usd * 100 * ledger.MICROCENTS_PER_CENT) and cached < plain


class _NoRows:
    """Session-Stub: keine Ledger-Zeilen -> Schaetzung aus Listenannahmen."""

    def scalars(self, *_args, **_kwargs):
        return []


def test_schaetzung_faellt_auf_listenpreise_zurueck(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("VISION_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("FLOW_MODEL_STRONG", "claude-sonnet-5")
    monkeypatch.setenv("CHAT_MODEL", "claude-sonnet-5")
    get_settings.cache_clear()
    try:
        result = ledger.estimate(_NoRows(), pages=300, photos=3)
    finally:
        get_settings.cache_clear()
    assert result["basis"] == {"vision.page": "list", "vision.cabinet": "list"}
    # cost-model.md: 300 Seiten mit Sonnet 5 = rund 2.4 USD; hier ohne Embeddings und Illustration
    assert 150 <= result["total_cents"] <= 400
    assert result["per_page_vision_cents"] > 0 and result["chat_per_answer_cents"] > 0
    assert ledger.estimate(_NoRows(), pages=0, photos=0)["total_cents"] == 0
    without_vision = ledger.estimate(_NoRows(), pages=300, photos=0, vision=False)
    assert without_vision["total_cents"] < result["total_cents"]


def test_month_start_ist_monatsanfang_utc():
    from datetime import datetime, timezone

    start = ledger.month_start(datetime(2026, 9, 27, 22, 5, tzinfo=timezone.utc))
    assert start == datetime(2026, 9, 1, tzinfo=timezone.utc)
