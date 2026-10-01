"""Eval-Harness: Bewertungslogik in eval/evallib.py (ohne Netz, ohne Modell)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "eval" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evallib = _load("evallib")

Q = {
    "id": "q1",
    "source": "S",
    "question": "?",
    "must_contain": ["-K3", "Blatt 4|S\\. 4"],
    "must_not_contain": ["Diagnoseadresse [0-9]{3,}"],
    "expect_sources": ["a.pdf"],
    "tools": ["find_tag"],
}


def test_score_counts_facts_sources_forbidden_and_tools():
    r = evallib.score(
        Q, "-K3 auf Blatt 4, Diagnoseadresse 1234", [{"filename": "a.pdf"}], ["find_tag"]
    )
    assert r["fakten"] == 1.0 and r["quellen_ok"] and not r["sauber"] and r["werkzeug_ok"] is True
    assert r["verboten_gefunden"] == ["Diagnoseadresse [0-9]{3,}"]


def test_score_tool_none_without_expectation():
    q = {**Q, "tools": []}
    assert evallib.score(q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["x"])["werkzeug_ok"] is None
    assert evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], None)["werkzeug_ok"] is None
    assert (
        evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["search_knowledge"])[
            "werkzeug_ok"
        ]
        is False
    )


def test_score_check_sources_false_ignores_expect_sources():
    r = evallib.score(Q, "-K3 Blatt 4", [], None, check_sources=False)
    assert r["quellen_ok"] and r["quellen_fehlend"] == []


def test_passed_requires_all():
    assert evallib.passed({"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None})
    assert not evallib.passed(
        {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": False}
    )
    assert not evallib.passed(
        {"fakten": 0.5, "quellen_ok": True, "sauber": True, "werkzeug_ok": True}
    )


def test_parse_sse_collects_answer_sources_tools_and_error():
    lines = [
        "event: conversation",
        'data: {"id": "c"}',
        "",
        "event: tool_start",
        'data: {"name": "find_tag", "args": {}}',
        "",
        "event: token",
        'data: {"text": "Hallo "}',
        "",
        "event: sources",
        'data: [{"filename": "a.pdf"}]',
        "",
        "event: token",
        'data: {"text": "Welt"}',
        "",
        "event: error",
        'data: {"message": "kaputt"}',
        "",
        "event: done",
        "data: {}",
        "",
        "event: token",
        'data: {"text": "danach"}',
        "",
    ]
    answer, sources, tools, meta = evallib.parse_sse(lines)
    assert answer == "Hallo Welt\n[FEHLER] kaputt"
    assert sources == [{"filename": "a.pdf"}] and tools == ["find_tag"]
    assert meta["conversation_id"] == "c"


def test_summarize_separates_errors():
    ok = {
        "answer": "x",
        "dauer_s": 2.0,
        "score": {"fakten": 0.5, "quellen_ok": True, "sauber": True, "werkzeug_ok": True},
    }
    bad = {
        "answer": "[FEHLER] Timeout",
        "dauer_s": 0.0,
        "score": {"fakten": 0.0, "quellen_ok": False, "sauber": True, "werkzeug_ok": None},
    }
    s = evallib.summarize([ok, bad])
    assert s["fragen"] == 2 and s["bewertet"] == 1 and s["nicht_bewertet_fehler"] == 1
    assert s["fakten_mittel"] == 0.5 and s["werkzeug_ok"] == 1.0 and s["voll_bestanden"] == 0


META = {
    "referenced_tags": ["-F2"],
    "citation_checks": [
        {
            "text": "[[a.pdf|/3.2]]",
            "file": "a.pdf",
            "locator": "/3.2",
            "valid": True,
            "checked": True,
            "reason": "",
        },
        {
            "text": "[[b.xlsx|-X3:3]]",
            "file": "b.xlsx",
            "locator": "-X3:3",
            "valid": False,
            "checked": True,
            "reason": "Kennzeichen -X3:3 nicht in b.xlsx",
        },
        {
            "text": "[[c.md|Kap. 7]]",
            "file": "c.md",
            "locator": "Kap. 7",
            "valid": True,
            "checked": False,
            "reason": "Ort nicht pruefbar: c.md hat keine Abschnitte",
        },
    ],
    "citations_valid": {"valid": 2, "checked": 2, "total": 3},
}


def test_parse_sse_collects_the_meta_event():
    lines = [
        "event: token",
        'data: {"text": "x"}',
        "",
        "event: meta",
        "data: " + json.dumps(META),
        "",
        "event: done",
        "data: {}",
        "",
    ]
    _answer, _sources, _tools, meta = evallib.parse_sse(lines)
    assert meta["answer_meta"] == META


def test_score_rates_citations_from_the_meta_event():
    # Anteil gueltiger unter den pruefbaren Belegen (1 von 2), Anteil pruefbarer Belege (2 von 3)
    r = evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["find_tag"], meta=META)
    assert (
        r["zitate_gueltig"] == 0.5
        and r["zitate_geprueft"] == pytest.approx(2 / 3)
        and r["zitate_belege"] == 3
    )
    assert r["zitate_ungueltig"] == ["[[b.xlsx|-X3:3]]"] and r["zitate_ungeprueft"] == [
        "[[c.md|Kap. 7]]"
    ]
    without = evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["find_tag"])
    assert (
        without["zitate_gueltig"] is None
        and without["zitate_geprueft"] is None
        and without["zitate_belege"] == 0
    )
    empty = evallib.score(
        Q,
        "ohne Beleg",
        [],
        None,
        meta={
            **META,
            "citation_checks": [],
            "citations_valid": {"valid": 0, "checked": 0, "total": 0},
        },
    )
    assert empty["zitate_gueltig"] is None and empty["zitate_belege"] == 0
    only_unchecked = evallib.score(
        Q, "x", [], None, meta={"citation_checks": [META["citation_checks"][2]]}
    )
    assert only_unchecked["zitate_gueltig"] is None and only_unchecked["zitate_geprueft"] == 0.0


def test_summarize_pools_citations_over_all_rated_rows():
    # Mikro-Definition wie contract.md "valid citations >= 95 %": Summe ueber alle Belege, nicht Mittel je Antwort
    base = {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None}
    rows = [
        {
            "answer": "a",
            "dauer_s": 1.0,
            "score": {**base, "zitate_belege": 4, "zitate_ungueltig": [], "zitate_ungeprueft": []},
        },
        {
            "answer": "b",
            "dauer_s": 1.0,
            "score": {
                **base,
                "zitate_belege": 4,
                "zitate_ungueltig": ["x", "y"],
                "zitate_ungeprueft": ["z"],
            },
        },
        {
            "answer": "c",
            "dauer_s": 1.0,
            "score": {**base, "zitate_belege": 0, "zitate_ungueltig": [], "zitate_ungeprueft": []},
        },
        {
            "answer": "[FEHLER] x",
            "dauer_s": 0.0,
            "score": {
                **base,
                "zitate_belege": 9,
                "zitate_ungueltig": list("abcdefghi"),
                "zitate_ungeprueft": [],
            },
        },
    ]
    s = evallib.summarize(rows)
    assert s["zitate_belege"] == 8 and s["zitate_antworten"] == 2
    assert s["zitate_gueltig"] == 0.714  # 5 gueltige von 7 pruefbaren (a: 4/4, b: 1/3)
    assert s["zitate_geprueft"] == 0.875  # 7 pruefbare von 8
    assert evallib.summarize([rows[2]])["zitate_gueltig"] is None
    assert "zitate_gueltig" in evallib.COMPARE_KEYS
    assert evallib.below_threshold({"zitate_gueltig": 0.9}, 0.95) is True
    assert evallib.below_threshold({"zitate_gueltig": None}, 0.5) is True
    assert evallib.below_threshold({"zitate_gueltig": 0.96}, 0.95) is False
    assert evallib.below_threshold({"zitate_gueltig": 0.5}, None) is False


def test_rescore_uses_stored_meta_or_asks_the_checker():
    rescore = _load("rescore")
    run = {
        "results": [
            {
                "id": "q1",
                "answer": "-K3 Blatt 4",
                "sources": [{"filename": "a.pdf"}],
                "tools": ["find_tag"],
                "meta": META,
            },
            {
                "id": "q1-alt",
                "answer": "-K3 Blatt 4",
                "sources": [{"filename": "a.pdf"}],
                "tools": ["find_tag"],
            },
        ]
    }
    questions = [Q, {**Q, "id": "q1-alt"}]
    asked = []

    def checker(row):
        asked.append(row["id"])
        return {
            "citation_checks": META["citation_checks"][:1],
            "citations_valid": {"valid": 1, "checked": 1, "total": 1},
        }

    summary, rows, _unknown = rescore.rescore(run, questions, checker=checker)
    assert asked == ["q1-alt"]
    assert [r["score"]["zitate_gueltig"] for r in rows] == [0.5, 1.0]
    assert rows[1]["meta"]["citations_valid"]["total"] == 1
    assert summary["zitate_gueltig"] == 0.667  # 2 gueltige von 3 pruefbaren Belegen
    plain, _rows, _ = rescore.rescore(run, questions)
    assert plain["zitate_gueltig"] == 0.5


def test_rescore_keeps_stored_checks_and_merges_new_ones_into_the_old_meta():
    rescore = _load("rescore")
    stored = {
        "referenced_tags": ["-K1"],
        "citation_checks": [],
        "citations_valid": {"valid": 0, "checked": 0, "total": 0},
    }
    run = {"results": [{"id": "q1", "answer": "x", "sources": [], "tools": [], "meta": stored}]}
    asked = []

    def checker(row):
        asked.append(row["id"])
        return {
            "citation_checks": META["citation_checks"][:1],
            "citations_valid": {"valid": 1, "checked": 1, "total": 1},
        }

    _summary, rows, _ = rescore.rescore(run, [Q], checker=checker)
    assert asked == [] and rows[0]["meta"] == stored
    without_checks = {
        "results": [
            {
                "id": "q1",
                "answer": "x",
                "sources": [],
                "tools": [],
                "meta": {"referenced_tags": ["-K1"]},
            }
        ]
    }
    _summary, rows, _ = rescore.rescore(without_checks, [Q], checker=checker)
    assert asked == ["q1"]
    assert (
        rows[0]["meta"]["referenced_tags"] == ["-K1"]
        and rows[0]["meta"]["citations_valid"]["total"] == 1
    )


def test_rescore_reports_expected_invalid_markers_that_were_not_flagged():
    rescore = _load("rescore")
    rows = [
        {"id": "q1", "score": {"zitate_ungueltig": ["[[b.xlsx|-X3:3]]"]}},
        {"id": "q2", "score": {"zitate_ungueltig": []}},
    ]
    assert rescore.missing_expected(rows, ["[[b.xlsx|-X3:3]]"]) == []
    assert rescore.missing_expected(rows, ["[[b.xlsx|-X3:3]]", "[[b.xlsx|-X4]]"]) == [
        "[[b.xlsx|-X4]]"
    ]


def test_load_questions_only_accepts_several_needles():
    rows = evallib.load_questions(
        ROOT / "eval" / "questions.jsonl", only="Foerderband FB-01,Injection-Test"
    )
    sources = {r["source"] for r in rows}
    assert sources == {"Foerderband FB-01", "Injection-Test"}
    assert (
        evallib.load_questions(ROOT / "eval" / "questions.jsonl", only=" festo , ,umroller")
        and True
    )


def test_injection_questions_are_traps_with_a_free_retrieval_check():
    rows = [
        r
        for r in evallib.load_questions(ROOT / "eval" / "questions.jsonl")
        if r["source"] == "Injection-Test"
    ]
    assert len(rows) == 5
    for row in rows:
        assert row["id"].startswith("inj-") and row.get("retrieval"), row["id"]
        assert row["must_not_contain"], row[
            "id"
        ]  # die eingebettete Anweisung darf nicht befolgt werden
        assert row["must_contain"], row["id"]  # und die echte Antwort steht trotzdem in der Doku
        assert row["expect_sources"] == ["Betriebsanleitung_Presse_P-02.md"]


def test_score_rates_referenced_parts_against_expect_tags():
    # Vertrag: referenced-part precision >= 0,85; erwartete Teile muessen genannt sein (Recall), zusaetzlich
    # genannte Teile sind nur richtig, wenn sie erwartet oder erlaubt sind (Praezision)
    q = {**Q, "expect_tags": ["-F2", "-M1"], "ok_tags": ["-K1"]}
    meta = {"referenced_tags": ["-f2", "-K1", "-X9"], "citation_checks": []}
    r = evallib.score(q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["find_tag"], meta=meta)
    assert r["teile_recall"] == 0.5 and r["teile_praezision"] == pytest.approx(2 / 3)
    assert r["teile_fehlend"] == ["-M1"] and r["teile_fremd"] == ["-X9"]
    assert (
        r["teile_erwartet"],
        r["teile_referenziert"],
        r["teile_treffer"],
        r["teile_passend"],
    ) == (2, 3, 1, 2)
    without_meta = evallib.score(q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["find_tag"])
    assert without_meta["teile_recall"] is None and without_meta["teile_praezision"] is None
    without_expectation = evallib.score(Q, "x", [], None, meta=meta)
    assert (
        without_expectation["teile_recall"] is None
        and without_expectation["teile_praezision"] is None
    )
    nothing_referenced = evallib.score(q, "x", [], None, meta={"referenced_tags": []})
    assert (
        nothing_referenced["teile_recall"] == 0.0 and nothing_referenced["teile_praezision"] is None
    )


def test_summarize_pools_parts_and_reports_p95_and_error_rate():
    base = {
        "fakten": 1.0,
        "quellen_ok": True,
        "sauber": True,
        "werkzeug_ok": None,
        "zitate_belege": 0,
        "zitate_ungueltig": [],
        "zitate_ungeprueft": [],
    }

    def parts(erwartet: int, referenziert: int, treffer: int, passend: int) -> dict:
        return {
            **base,
            "teile_erwartet": erwartet,
            "teile_referenziert": referenziert,
            "teile_treffer": treffer,
            "teile_passend": passend,
        }

    rows = [
        {"answer": "a", "dauer_s": 10.0, "score": parts(2, 3, 1, 2)},
        {"answer": "b", "dauer_s": 20.0, "score": parts(2, 2, 2, 2)},
        {
            "answer": "c",
            "dauer_s": 30.0,
            "score": {
                **base,
                "teile_erwartet": 0,
                "teile_referenziert": 4,
                "teile_treffer": 0,
                "teile_passend": 0,
            },
        },  # keine Erwartung: zaehlt nicht
        {"answer": "[FEHLER] x", "dauer_s": 0.0, "score": parts(9, 9, 0, 0)},
    ]
    s = evallib.summarize(rows)
    assert s["teile_recall"] == 0.75  # 3 Treffer von 4 erwarteten
    assert (
        s["teile_praezision"] == 0.8
    )  # 4 passende von 5 referenzierten (Zeile c ohne Erwartung bleibt aussen vor)
    assert s["p95_s"] == 30.0 and s["fehlerrate"] == 0.25
    assert evallib.summarize([rows[3]])["p95_s"] is None
    for key in ("teile_praezision", "teile_recall", "p95_s", "fehlerrate"):
        assert key in evallib.COMPARE_KEYS


def test_validate_questions_checks_expect_and_ok_tags():
    ok = {**Q, "expect_tags": ["-F2"], "ok_tags": ["-K1"]}
    assert evallib.validate_questions([ok]) == []
    bad = {**Q, "expect_tags": "-F2"}
    assert any("expect_tags" in p for p in evallib.validate_questions([bad]))
    bad_ok = {**Q, "ok_tags": [""]}
    assert any("ok_tags" in p for p in evallib.validate_questions([bad_ok]))


def test_fb01_golden_set_has_twenty_questions_with_expected_parts():
    rows = [
        r
        for r in evallib.load_questions(ROOT / "eval" / "questions.jsonl")
        if r["source"] == "Foerderband FB-01"
    ]
    assert len(rows) >= 20
    for row in rows:
        assert "expect_sources" in row and isinstance(row["expect_sources"], list), row["id"]
        assert row.get("expect_tags"), row["id"]
        assert all(t.startswith("-") for t in row["expect_tags"] + row.get("ok_tags", [])), row[
            "id"
        ]
    with_retrieval = [r for r in rows if r.get("retrieval")]
    assert len(with_retrieval) >= 18  # nur Fallenfragen ohne Retrieval-Anteil


def test_api_checker_resolves_the_source_and_posts_answer_with_its_sources():
    import httpx

    rescore = _load("rescore")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/sources":
            return httpx.Response(200, json=[{"id": "s1", "name": "Foerderband FB-01"}])
        seen["path"], seen["body"] = request.url.path, json.loads(request.content)
        return httpx.Response(
            200,
            json={"citation_checks": [], "citations_valid": {"valid": 0, "checked": 0, "total": 0}},
        )

    check = rescore.api_checker("http://test", transport=httpx.MockTransport(handler))
    result = check(
        {
            "source": "Foerderband FB-01",
            "answer": "a [[a.pdf|S. 3]]",
            "sources": [{"filename": "a.pdf", "page": 3, "document_id": "d"}],
        }
    )
    assert result == {
        "citation_checks": [],
        "citations_valid": {"valid": 0, "checked": 0, "total": 0},
    }
    assert seen == {
        "path": "/api/answers/validate-citations",
        "body": {
            "answer": "a [[a.pdf|S. 3]]",
            "source_ids": ["s1"],
            "sources": [{"filename": "a.pdf"}],
        },
    }
    assert check({"source": "Unbekannt", "answer": "a", "sources": []}) is None


def test_summarize_werkzeug_none_without_expectations():
    row = {
        "answer": "x",
        "dauer_s": 1.0,
        "score": {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None},
    }
    assert evallib.summarize([row])["werkzeug_ok"] is None


def test_validate_reports_bad_regex_and_duplicates():
    rows = [{**Q, "must_contain": ["("]}, {**Q}]
    problems = evallib.validate_questions(rows)
    assert any("q1" in p and "(" in p for p in problems)
    assert any("doppelt" in p for p in problems)


def test_validate_agent_false_needs_retrieval_and_mode_known():
    rows = [
        {**Q, "id": "a", "agent": False},
        {**Q, "id": "b", "retrieval": {"mode": "magic", "query": "x"}},
    ]
    problems = evallib.validate_questions(rows)
    assert any(p.startswith("a:") and "retrieval" in p for p in problems)
    assert any("magic" in p for p in problems)


def test_compare_lists_deltas():
    rows = evallib.compare(
        {"fakten_mittel": 0.9, "sauber": 1.0}, {"fakten_mittel": 0.8, "sauber": 1.0}
    )
    assert ("fakten_mittel", 0.8, 0.9, 0.1) in [(k, a, b, round(d, 3)) for k, a, b, d in rows]


def test_write_result_names_file(tmp_path):
    out = evallib.write_result(tmp_path, "retrieval_", {"a": 1}, [])
    assert out.name.startswith("retrieval_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8"))["summary"] == {"a": 1}


def test_load_questions_raises_on_problems(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps({**Q, "must_contain": ["("]}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="q1"):
        evallib.load_questions(path)


def test_questions_file_is_valid():
    rows = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    assert len(rows) >= 24
    assert evallib.load_questions(ROOT / "eval" / "questions.jsonl", only="festo")


# --- Task 2: Retrieval-Schicht ------------------------------------------------------------------


def test_flatten_search_uses_text_and_ref_filenames():
    refs = [{"filename": "a.pdf"}, {"filename": "a.pdf"}, {"filename": "b.csv"}]
    text, files = evallib.flatten("tag", {"text": "Fundstellen", "refs": refs})
    assert text == "Fundstellen" and files == ["a.pdf", "b.csv"]


def test_flatten_fact_card_lines_and_files():
    card = {
        "tag": "-M1",
        "title": "Motor",
        "bom_line": "-M1 | Motor",
        "rows": [
            {
                "label": "Klemmen",
                "values": [
                    {"text": "-X4:U", "ref": "-X4:U", "filename": "03.csv"},
                    {"text": "-X4:V", "ref": "", "filename": "03.csv"},
                ],
            }
        ],
    }
    text, files = evallib.flatten("fact", card)
    assert "Klemmen: -X4:U, -X4:V" in text and "Motor" in text and files == ["03.csv"]


def test_flatten_signal_lists_nodes():
    path = {
        "start": "-S1",
        "edges": [],
        "nodes": [
            {"id": "FB 10/NW1", "label": "Selbsthaltung", "ref": "FB 10 NW 1", "detail": "U #Start"}
        ],
    }
    text, files = evallib.flatten("signal", path)
    assert "FB 10/NW1 | Selbsthaltung | FB 10 NW 1" in text and "U #Start" in text and files == []


def test_flatten_calc_and_site_dump_json():
    assert '"pallets": 160' in evallib.flatten("calc", {"summary": {"pallets": 160}})[0]
    assert evallib.flatten("site", None) == ("", [])
    assert '"docks": 8' in evallib.flatten("site", {"name": "Lager", "docks": 8})[0]


def test_flatten_site_unknown_hall():
    rr = _load("run_retrieval")
    assert rr.find_hall({"halls": [{"name": "Verarbeitung"}]}, "Lager") is None
    assert (
        rr.find_hall({"halls": [{"name": "Lager & Versand"}]}, "lager")["name"] == "Lager & Versand"
    )


def test_run_retrieval_unknown_article():
    rr = _load("run_retrieval")
    with pytest.raises(ValueError, match="XX-1"):
        rr.calc_body(
            {"positions": [{"article": "XX-1", "quantity": 1, "unit": "unit"}]}, {"TP-1": "id1"}
        )
    body = rr.calc_body(
        {
            "received_at": "2026-09-28T07:00",
            "positions": [{"article": "TP-1", "quantity": 2, "unit": "pallet"}],
        },
        {"TP-1": "id1"},
    )
    assert body["positions"] == [{"article_id": "id1", "quantity": 2, "unit": "pallet"}]
    assert body["received_at"] == "2026-09-28T07:00"


# --- Task 3: Wiederbewertung --------------------------------------------------------------------


def test_rescore_reproduces_reference_run():
    rescore = _load("rescore")
    run = json.loads(
        (ROOT / "eval" / "results" / "referenz_2026-09-26.json").read_text(encoding="utf-8")
    )
    questions = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    summary, rows, unknown = rescore.rescore(run, questions)
    assert unknown == [] and summary["fragen"] == len(run["results"])
    for old, new in zip(run["results"], rows, strict=True):
        assert new["id"] == old["id"]
        assert (
            new["score"]["fakten"] == old["score"]["fakten"]
            and new["score"]["sauber"] == old["score"]["sauber"]
        )


def test_rescore_without_tools():
    rescore = _load("rescore")
    run = {
        "results": [
            {
                "id": "q1",
                "answer": "-K3 Blatt 4",
                "sources": [{"filename": "a.pdf"}],
                "dauer_s": 1.0,
            }
        ]
    }
    summary, rows, unknown = rescore.rescore(run, [Q])
    assert rows[0]["score"]["werkzeug_ok"] is None and summary["werkzeug_ok"] is None


def test_rescore_counts_unknown_ids():
    rescore = _load("rescore")
    run = {"results": [{"id": "zz", "answer": "x", "sources": [], "dauer_s": 1.0}]}
    summary, rows, unknown = rescore.rescore(run, [Q])
    assert unknown == ["zz"] and rows == [] and summary["fragen"] == 0


# --- Task 4: Fragen ------------------------------------------------------------------------------


def test_questions_cover_testdoku_and_testwerk():
    rows = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    by_source: dict[str, list[dict]] = {}
    for r in rows:
        by_source.setdefault(r.get("source") or "Testwerk", []).append(r)
    assert len(by_source["Umroller UR-01"]) >= 10 and len(by_source["Aufrollung PM1-AR"]) >= 9
    assert len([r for r in rows if r.get("agent") is False]) >= 4
    assert sum(1 for r in rows if r.get("retrieval")) >= 30
    assert all(
        r["id"].endswith("nicht-vorhanden")
        for r in rows
        if not r["expect_sources"] and r.get("agent", True)
    )
    assert all(r["must_not_contain"] for r in rows if r["id"].endswith("nicht-vorhanden"))


def test_scan_fragen_pruefen_den_voll_scan_und_bleiben_aus_dem_fb01_filter():
    """Issue #66: Die Quelle heisst nicht "Foerderband FB-01 (Scan)", weil --only per Teiltext filtert und der
    woechentliche Agentenlauf (--only "Foerderband FB-01,...") die Fragen sonst ohne geladene Quelle stellen wuerde."""
    rows = [
        r
        for r in evallib.load_questions(ROOT / "eval" / "questions.jsonl")
        if r["source"] == "Scan FB-01"
    ]
    assert len(rows) == 5 and all(r["id"].startswith("fb01-scan-") for r in rows)
    assert all(
        r["retrieval"] and r["expect_sources"] == ["01_Stromlaufplan_FB-01_scan.pdf"] for r in rows
    )
    assert not evallib.load_questions(
        ROOT / "eval" / "questions.jsonl", only="Foerderband FB-01,Injection-Test"
    )[-1]["id"].startswith("fb01-scan-")
    fb01 = evallib.load_questions(ROOT / "eval" / "questions.jsonl", only="Foerderband FB-01")
    assert {r["source"] for r in fb01} == {"Foerderband FB-01"}


# --- Fix pass nach Review ------------------------------------------------------------------------


def test_is_error_detects_streamed_error_event():
    answer, _, _, _ = evallib.parse_sse(
        [
            "event: token",
            'data: {"text": "Ich schaue nach."}',
            "",
            "event: error",
            'data: {"message": "Guthaben erschoepft"}',
            "",
        ]
    )
    assert evallib.is_error({"answer": answer})
    assert not evallib.is_error({"answer": "Der Fehler liegt an -F2."})


def test_rescore_reference_run_counts_streamed_errors_and_full_summary():
    rescore = _load("rescore")
    run = json.loads(
        (ROOT / "eval" / "results" / "referenz_2026-09-26.json").read_text(encoding="utf-8")
    )
    summary, rows, _ = rescore.rescore(
        run, evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    )
    assert summary["nicht_bewertet_fehler"] == 5 and summary["bewertet"] == 19
    assert summary["voll_bestanden"] == run["summary"]["voll_bestanden"] == 19
    assert summary["quellen_ok"] == 1.0 and summary["sauber"] == 1.0
    for old, new in zip(run["results"], rows, strict=True):
        assert new["score"]["quellen_ok"] == old["score"]["quellen_ok"]


def test_rescore_retrieval_run_skips_sources_for_modes_without_files():
    rescore = _load("rescore")
    run = json.loads(
        (ROOT / "eval" / "results" / "referenz_retrieval_2026-09-27.json").read_text(
            encoding="utf-8"
        )
    )
    summary, rows, unknown = rescore.rescore(
        run, evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    )
    assert unknown == [] and summary["quellen_ok"] == 1.0 and summary["voll_bestanden"] == 31


def test_retrieval_http_and_value_errors_are_scored_as_failures():
    import httpx

    rr = _load("run_retrieval")
    response = httpx.Response(
        404, json={"detail": "-S99 kommt nicht vor"}, request=httpx.Request("GET", "http://x")
    )
    text = rr.answer_for_error(
        httpx.HTTPStatusError("404", request=response.request, response=response)
    )
    assert not evallib.is_error({"answer": text}) and "404" in text and "-S99" in text
    assert not evallib.is_error({"answer": rr.answer_for_error(ValueError("Artikel XX unbekannt"))})
    assert evallib.is_error({"answer": rr.answer_for_error(httpx.ConnectError("zu"))})


def test_retrieval_gate_fails_on_unscored_errors():
    rr = _load("run_retrieval")
    assert rr.gate_failed({"fakten_mittel": 1.0, "nicht_bewertet_fehler": 3}, 0.9)
    assert rr.gate_failed({"fakten_mittel": 0.8, "nicht_bewertet_fehler": 0}, 0.9)
    assert not rr.gate_failed({"fakten_mittel": 1.0, "nicht_bewertet_fehler": 0}, 0.9)
    assert not rr.gate_failed({"fakten_mittel": 0.0, "nicht_bewertet_fehler": 3}, 0.0)


# --- Verbrauch und Kosten ------------------------------------------------------------------------


def test_parse_sse_summiert_usage_je_modellaufruf():
    lines = [
        "event: conversation",
        'data: {"id": "c7"}',
        "",
        "event: usage",
        'data: {"input_tokens": 1200, "output_tokens": 80, "model": "claude-sonnet-5-20260115"}',
        "",
        "event: token",
        'data: {"text": "Moment"}',
        "",
        "event: usage",
        'data: {"input_tokens": 300, "output_tokens": 20, "model": "claude-sonnet-5-20260115"}',
        "",
        "event: done",
        "data: {}",
        "",
    ]
    _, _, _, meta = evallib.parse_sse(lines)
    assert meta["usage"] == {
        "input_tokens": 1500,
        "output_tokens": 100,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "calls": 2,
        "model": "claude-sonnet-5-20260115",
    }


def test_usage_total_nur_wenn_verbrauch_vorliegt():
    assert evallib.usage_total([{"answer": "x"}]) == {}
    rows = [
        {
            "answer": "a",
            "usage": {"input_tokens": 100, "output_tokens": 10, "calls": 1, "cost_usd": 0.0003},
        },
        {
            "answer": "b",
            "usage": {"input_tokens": 200, "output_tokens": 20, "calls": 2, "cost_usd": 0.0006},
        },
    ]
    assert evallib.usage_total(rows) == {
        "tokens_ein": 300,
        "tokens_aus": 30,
        "modellaufrufe": 3,
        "kosten_usd": 0.0009,
    }


def test_summarize_nimmt_kosten_auf():
    rows = [
        {
            "answer": "a",
            "dauer_s": 1.0,
            "usage": {"input_tokens": 1_000_000, "output_tokens": 0, "calls": 1, "cost_usd": 2.0},
            "score": {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None},
        }
    ]
    summary = evallib.summarize(rows)
    assert summary["kosten_usd"] == 2.0 and summary["tokens_ein"] == 1_000_000


def test_preis_auch_fuer_datierte_modell_id():
    from app.flow.pricing import cost_usd, prices_for

    assert prices_for("claude-sonnet-5") == prices_for("claude-sonnet-5-20260115")
    assert prices_for("gpt-irgendwas") is None
    assert cost_usd("claude-sonnet-5-20260115", 1_000_000, 0) == 2.0
    assert cost_usd("unbekannt", 1_000_000, 1_000_000) == 0.0


def test_preis_mit_prompt_cache():
    from app.flow.pricing import cost_usd

    # gpt-5-mini: 0,25 USD/M Eingabe, Cache-Treffer ein Zehntel; Anthropic schreibt mit 1,25-fachem Preis
    assert cost_usd("openai:gpt-5-mini", 1_000_000, 0, cache_read=1_000_000) == 0.025
    assert cost_usd("claude-sonnet-5", 1_000_000, 0, cache_creation=1_000_000) == 2.5
    assert cost_usd("claude-sonnet-5", 1_000_000, 0, cache_read=500_000) == 1.1


def test_preise_der_modelle_vom_2026_10_02():
    """Offizielle Listen (platform.claude.com/docs/en/about-claude/pricing, developers.openai.com/api/docs/pricing):
    Cache-Treffer kosten meist ein Zehntel, bei Opus 5.5 und gpt-6.1-sol ein Zwanzigstel."""
    from app.flow.pricing import cost_usd, prices_for

    assert prices_for("claude-opus-5-5-20260901")[:2] == (4.0, 20.0)
    assert prices_for("claude-sonnet-5-5")[:2] == (2.0, 10.0)
    assert cost_usd("claude-opus-5-5", 1_000_000, 0, cache_read=1_000_000) == 0.2
    assert cost_usd("claude-opus-5-5", 1_000_000, 0, cache_creation=1_000_000) == 5.0
    assert cost_usd("openai:gpt-6.1-sol", 1_000_000, 0, cache_read=1_000_000) == 0.1
    assert cost_usd("openai:gpt-6-astra", 1_000_000, 1_000_000) == 60.0
    assert cost_usd("openai:gpt-5.6-terra-2026-06-01", 1_000_000, 1_000_000) == 14.0
    assert cost_usd("openai:gpt-5.5", 1_000_000, 0) == 5.0  # nicht der gpt-5-Preis
    assert cost_usd("openai:gpt-5.4-mini", 1_000_000, 0, cache_read=1_000_000) == 0.075
    assert cost_usd("ollama:qwen3.5:4b", 1_000_000, 1_000_000) == 0.0 and prices_for(
        "ollama:qwen3.5:4b"
    ) == (0.0, 0.0, 0.0)


def test_run_eval_schreibt_wahlweise_in_eine_genannte_datei(tmp_path):
    run_eval = _load("run_eval")
    assert run_eval.output_path(None, "lauf_1") == run_eval.RESULTS / "lauf_1.json"
    assert run_eval.output_path(tmp_path / "haiku.json", "lauf_1") == tmp_path / "haiku.json"


def test_parse_sse_summiert_cache_tokens_und_ask_rechnet_sie_ein():
    lines = [
        "event: usage",
        'data: {"input_tokens": 1000, "output_tokens": 10, "model": "claude-sonnet-5", "cache_read_tokens": 800, "cache_creation_tokens": 100}',
        "event: usage",
        'data: {"input_tokens": 1000, "output_tokens": 10, "model": "claude-sonnet-5", "cache_read_tokens": 900}',
        "event: done",
        "data: {}",
    ]
    _, _, _, meta = evallib.parse_sse(lines)
    assert (
        meta["usage"]["cache_read_tokens"] == 1700 and meta["usage"]["cache_creation_tokens"] == 100
    )
    run_eval = _load("run_eval")
    assert run_eval.usage_cost(meta["usage"]) == pytest.approx(
        (200 * 2.0 + 1700 * 0.2 + 100 * 2.5 + 20 * 10.0)
        / 1_000_000  # 2000 Eingabe, 200 davon frisch
    )


def test_save_result_ueberschreibt_dieselbe_datei(tmp_path):
    out = tmp_path / "lauf.json"
    rows = [
        {
            "id": "a",
            "answer": "x",
            "dauer_s": 1.0,
            "score": {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None},
        }
    ]
    evallib.save_result(out, evallib.summarize(rows), rows)
    rows.append(
        {
            "id": "b",
            "answer": "y",
            "dauer_s": 1.0,
            "score": {"fakten": 0.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None},
        }
    )
    evallib.save_result(out, evallib.summarize(rows), rows)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert [r["id"] for r in saved["results"]] == ["a", "b"] and saved["summary"]["fragen"] == 2
