"""Planleser per Modell (app/ingestion/plan_model.py, Spur D): Eingabe, Pruefung, Schaetzung und Lauf mit einem
Modell-Fake an der Stelle von make_chat_model. Kein Netz, kein Schluessel, kein Modellaufruf."""

from pathlib import Path

import pytest
from plan_model_fake import LIMIT_TOKENS, MODEL_ID, FakeModel, edge

from app.ingestion import plan_model
from app.ingestion.plan_edges import PlanEdge

FB01 = (
    Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
)
PAGE4_TAGS = {"-S1", "-S1:13", "-S1:14", "-X3", "-X3:1", "-X3:2", "E0.0", "E0.1", "-K3", "-K3:13"}


def _modell(source, target, directed=False, page=4):
    return PlanEdge(source, target, page, "modell", directed)


def test_validate_behaelt_nur_enden_aus_den_kennzeichen_der_seite():
    kept, dropped = plan_model.validate(
        [
            _modell("-S1:13", "-X3:1"),
            _modell("-X3:1", "E0.0", directed=True),
            _modell("-S9", "-X3:1"),  # -S9 steht nicht auf der Seite
            _modell("-X3:1", "MOTOR"),  # kein Kennzeichen
            _modell("-X3:2", "-X3:2"),  # Schleife
        ],
        PAGE4_TAGS,
    )
    assert kept == [_modell("-S1:13", "-X3:1"), _modell("-X3:1", "E0.0", directed=True)]
    assert dropped == [
        _modell("-S9", "-X3:1"),
        _modell("-X3:1", "MOTOR"),
        _modell("-X3:2", "-X3:2"),
    ]


def test_validate_nimmt_anschluesse_ueber_ihr_schaltgeraet_und_legt_doppelte_zusammen():
    kept, dropped = plan_model.validate(
        [
            _modell("-K3:23", "E0.1"),  # 23/24 nicht im Index, aber Schliesser an -K3
            _modell("E0.1", "-K3:23"),  # ungerichtet doppelt
            _modell("-X3:9", "E0.1"),  # Klemme 9 gibt es nicht: Klemmen zaehlen nur mit Index
            _modell("-S1:A1", "E0.1"),  # Taster hat keine Spule
        ],
        PAGE4_TAGS,
    )
    assert kept == [_modell("-K3:23", "E0.1")]
    assert [(e.source, e.target) for e in dropped] == [("-X3:9", "E0.1"), ("-S1:A1", "E0.1")]


def test_estimate_usd_rechnet_3000_rein_und_2000_raus_je_seite():
    # gpt-4.1-mini: 0,40 USD je 1M rein, 1,60 USD je 1M raus -> 0,0044 USD je Seite
    assert plan_model.output_tokens_per_page("openai:gpt-4.1-mini") == 2000
    assert plan_model.estimate_usd("openai:gpt-4.1-mini", 1) == pytest.approx(0.0044)
    assert plan_model.estimate_usd("claude-sonnet-5", 1) == pytest.approx(0.026)
    assert plan_model.estimate_usd("openai:qwen3.5:4b", 23) == 0.0  # unbekannt, etwa lokal


def test_reasoning_modelle_werden_mit_4000_ausgabe_token_je_seite_geschaetzt():
    """Erster Lehrerlauf: gpt-5-mini kostete auf FB-01 0,0523 USD statt geschaetzter 0,033 (7 Seiten)."""
    assert plan_model.output_tokens_per_page("openai:gpt-5-mini") == 4000
    assert plan_model.output_tokens_per_page("o3-mini") == 4000
    # gpt-5-mini: 3000 x 0,25 + 4000 x 2,00 je 1M -> 0,00875 USD je Seite
    assert plan_model.estimate_usd("openai:gpt-5-mini", 1) == pytest.approx(0.00875)
    assert plan_model.estimate_usd("openai:gpt-5-mini", 7) == pytest.approx(0.06125)
    assert plan_model.estimate_usd("openai:gpt-5-mini", 7) > 0.0523  # ueber dem Messwert
    assert plan_model.estimate_usd("openai:gpt-5-mini", 23) == pytest.approx(0.20125)
    assert plan_model.estimate_usd("gpt-5-mini", 0) == 0.0


def test_page_payload_hat_bild_wortliste_und_kennzeichen_ohne_modell():
    payload = plan_model.page_payload(FB01, 4, ["E0.0", "-S1", "-S1"])
    assert payload["png"].startswith(b"\x89PNG")
    assert (payload["page"], payload["width"], payload["height"], payload["angle"]) == (
        4,
        842,
        595,
        0,
    )
    assert payload["tags"] == ["-S1", "E0.0"]
    words = {text for text, _x, _y in payload["words"]}
    assert {"-S1", "E0.0"} <= words
    assert all(0 <= x <= 842 and 0 <= y <= 595 for _t, x, y in payload["words"])
    text = plan_model.prompt_text(payload)
    assert "Bekannte Kennzeichen dieser Seite (2): -S1, E0.0" in text
    assert "<wortliste>" in text and "Seite 4, 842 x 595 pt" in text


def test_to_edges_setzt_anschluss_schreibweise_und_richtung():
    payload = {"page": 4, "tags": sorted(PAGE4_TAGS)}
    edges = plan_model.to_edges(
        [
            edge("-s1", "-x3:1", pins=("13", None), directed=True),
            edge("-X3", "E0.0", pins=("2", None)),
            edge("-M1", "-X3:1", pins=("U1", None), directed="ja"),
        ],
        payload,
    )
    assert edges == [
        PlanEdge("-S1:13", "-X3:1", 4, "modell", True),
        PlanEdge("-X3:2", "E0.0", 4, "modell", False),
        PlanEdge("-M1", "-X3:1", 4, "modell", False),  # U1 sagt bei -M1 nichts, Richtung unklar
    ]


def test_make_model_geht_ueber_make_chat_model(monkeypatch):
    seen = {}
    fake = FakeModel()

    def fake_make_chat_model(name, **kwargs):
        seen.update(kwargs, name=name)
        return fake

    monkeypatch.setattr(plan_model, "make_chat_model", fake_make_chat_model)
    assert plan_model.make_model("openai:qwen3.5:4b", "http://localhost:11434/v1") is fake
    assert seen["name"] == "openai:qwen3.5:4b" and seen["base_url"] == "http://localhost:11434/v1"
    assert seen["max_tokens"] == plan_model.MAX_TOKENS
    assert seen["reasoning_effort"] is None  # lokales Modell ohne Reasoning-Parameter
    plan_model.make_model("openai:gpt-5-mini")
    assert seen["base_url"] is None and seen["reasoning_effort"] == "low"
    plan_model.make_model("claude-sonnet-5")
    assert seen["reasoning_effort"] is None


def test_read_page_with_model_fragt_mit_json_schema_und_liefert_ungepruefte_kanten():
    fake = FakeModel({4: {"edges": [edge("-S1", "-X3:1", pins=("13", None)), edge("-S9", "E0.0")]}})
    payload = {
        "page": 4,
        "png": b"\x89PNG",
        "width": 842,
        "height": 595,
        "angle": 0,
        "words": [("-S1", 100, 200)],
        "tags": sorted(PAGE4_TAGS),
    }
    edges = plan_model.read_page_with_model(fake, payload)
    assert edges == [
        PlanEdge("-S1:13", "-X3:1", 4, "modell", False),
        PlanEdge("-S9", "E0.0", 4, "modell", False),
    ]
    schema, kwargs = fake.structured
    assert schema is plan_model.EDGE_SCHEMA
    assert kwargs == {"method": "json_schema", "include_raw": True, "strict": True}
    assert "-S1 100 200" in fake.prompts[4]


def test_ohne_strukturierte_ausgabe_liest_der_planleser_das_json_aus_dem_rohtext():
    fake = FakeModel({4: {"edges": [edge("-S1", "-X3:1")]}}, parsed=False)
    payload = {
        "page": 4,
        "png": b"",
        "width": 1,
        "height": 1,
        "angle": 0,
        "words": [],
        "tags": ["-S1", "-X3:1"],
    }
    assert plan_model.read_page_with_model(fake, payload) == [
        PlanEdge("-S1", "-X3:1", 4, "modell", False)
    ]


def test_read_pages_liest_parallel_prueft_und_zaehlt_tokens(monkeypatch):
    fake = FakeModel(
        {
            3: {"edges": [edge("-K1", "-X4:U"), edge("-K1", "-Q9")]},
            4: {
                "edges": [
                    edge("-S1", "-X3:1", pins=("13", None), reason="Leitung von 13 nach X3:1")
                ]
            },
        },
        fail_pages={5},
    )
    tags = {
        1: {"-A1"},  # nur ein Kennzeichen: geht nicht ans Modell
        3: {"-K1", "-X4:U"},
        4: PAGE4_TAGS,
        5: {"-K1", "-K2"},
    }
    reads = plan_model.read_pages(fake, FB01, tags, model_name="openai:gpt-5-mini", workers=2)
    assert sorted(fake.calls) == [3, 4, 5]
    by_page = {read.page: read for read in reads}
    assert [r.page for r in reads] == [3, 4, 5]
    assert by_page[3].kept == [PlanEdge("-K1", "-X4:U", 3, "modell", False)]
    assert [(e.source, e.target) for e in by_page[3].dropped] == [("-K1", "-Q9")]
    assert by_page[4].reasons[("-S1:13", "-X3:1")] == "Leitung von 13 nach X3:1"
    assert by_page[5].error == "RuntimeError: Anbieter nicht erreichbar" and by_page[5].kept == []
    usage = plan_model.total_usage(reads)
    assert (usage.model, usage.input_tokens, usage.output_tokens) == (MODEL_ID, 6200, 900)
    # echte Kosten aus den Tokens (datierte ID -> gpt-5-mini), lokal kostenlos, ohne Tokens unbekannt
    assert plan_model.run_cost_usd(usage) == pytest.approx((6200 * 0.25 + 900 * 2.0) / 1_000_000)
    assert plan_model.run_cost_usd(usage, "http://localhost:11434/v1") == 0.0
    assert plan_model.run_cost_usd(None) is None


def test_laengenlimit_ist_eine_gescheiterte_seite_mit_grund_und_bezahlten_tokens():
    """openai.LengthFinishReasonError (alle 8000 Token fuers Nachdenken) bricht den Lauf nicht ab."""
    fake = FakeModel({3: {"edges": [edge("-K1", "-X4:U")]}}, length_pages={4}, cut_pages={5})
    tags = {3: {"-K1", "-X4:U"}, 4: PAGE4_TAGS, 5: {"-K1", "-K2"}}
    reads = plan_model.read_pages(fake, FB01, tags, model_name="openai:gpt-5-mini", workers=3)
    by_page = {read.page: read for read in reads}
    assert by_page[3].error is None and len(by_page[3].kept) == 1
    assert by_page[4].error == plan_model.LENGTH_LIMIT == "Laengenlimit"
    assert by_page[5].error == plan_model.LENGTH_LIMIT  # abgeschnittene Antwort ohne JSON
    # Tokens der Seite am Limit stehen nur am Fehler; sie sind bezahlt und zaehlen mit
    assert (by_page[4].usage.input_tokens, by_page[4].usage.output_tokens) == LIMIT_TOKENS
    assert (by_page[5].usage.input_tokens, by_page[5].usage.output_tokens) == (3100, 450)
    total = plan_model.total_usage(reads)
    assert (total.input_tokens, total.output_tokens) == (3100 + 3200 + 3100, 450 + 8000 + 450)


def test_ohne_gemeldete_tokens_bleiben_die_kosten_unbekannt():
    fake = FakeModel({3: {"edges": []}}, report_usage=False)
    reads = plan_model.read_pages(fake, FB01, {3: {"-K1", "-X4:U"}}, model_name="openai:gpt-5-mini")
    assert plan_model.total_usage(reads) is None


def test_schema_passt_zu_openai_strikt_und_zu_anthropic_ohne_aufruf():
    """Nur Aufbau der LangChain-Runnables mit Platzhalter-Schluesseln, keine Anfrage."""
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    openai = ChatOpenAI(model="gpt-5-mini", api_key="x", base_url="http://127.0.0.1:9/v1")
    runnable = openai.with_structured_output(
        plan_model.EDGE_SCHEMA, method="json_schema", include_raw=True, strict=True
    )
    response_format = runnable.first.steps__["raw"].kwargs["response_format"]["json_schema"]
    assert response_format["strict"] is True and response_format["name"] == "planleser_kanten"
    items = response_format["schema"]["properties"]["edges"]["items"]
    assert sorted(items["required"]) == ["directed", "from", "pins", "reason", "to"]

    anthropic = ChatAnthropic(model="claude-sonnet-5", api_key="x")
    runnable = anthropic.with_structured_output(
        plan_model.EDGE_SCHEMA, method="json_schema", include_raw=True, strict=True
    )
    output = runnable.first.steps__["raw"].kwargs["output_config"]["format"]
    assert output["type"] == "json_schema"
    assert "pins" in output["schema"]["properties"]["edges"]["items"]["properties"]
