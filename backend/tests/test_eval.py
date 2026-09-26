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
    r = evallib.score(Q, "-K3 auf Blatt 4, Diagnoseadresse 1234", [{"filename": "a.pdf"}], ["find_tag"])
    assert r["fakten"] == 1.0 and r["quellen_ok"] and not r["sauber"] and r["werkzeug_ok"] is True
    assert r["verboten_gefunden"] == ["Diagnoseadresse [0-9]{3,}"]


def test_score_tool_none_without_expectation():
    q = {**Q, "tools": []}
    assert evallib.score(q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["x"])["werkzeug_ok"] is None
    assert evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], None)["werkzeug_ok"] is None
    assert evallib.score(Q, "-K3 Blatt 4", [{"filename": "a.pdf"}], ["search_knowledge"])["werkzeug_ok"] is False


def test_score_check_sources_false_ignores_expect_sources():
    r = evallib.score(Q, "-K3 Blatt 4", [], None, check_sources=False)
    assert r["quellen_ok"] and r["quellen_fehlend"] == []


def test_passed_requires_all():
    assert evallib.passed({"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None})
    assert not evallib.passed({"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": False})
    assert not evallib.passed({"fakten": 0.5, "quellen_ok": True, "sauber": True, "werkzeug_ok": True})


def test_parse_sse_collects_answer_sources_tools_and_error():
    lines = [
        "event: conversation", 'data: {"id": "c"}', "",
        "event: tool_start", 'data: {"name": "find_tag", "args": {}}', "",
        "event: token", 'data: {"text": "Hallo "}', "",
        "event: sources", 'data: [{"filename": "a.pdf"}]', "",
        "event: token", 'data: {"text": "Welt"}', "",
        "event: error", 'data: {"message": "kaputt"}', "",
        "event: done", "data: {}", "",
        "event: token", 'data: {"text": "danach"}', "",
    ]
    answer, sources, tools = evallib.parse_sse(lines)
    assert answer == "Hallo Welt\n[FEHLER] kaputt"
    assert sources == [{"filename": "a.pdf"}] and tools == ["find_tag"]


def test_summarize_separates_errors():
    ok = {"answer": "x", "dauer_s": 2.0, "score": {"fakten": 0.5, "quellen_ok": True, "sauber": True, "werkzeug_ok": True}}
    bad = {"answer": "[FEHLER] Timeout", "dauer_s": 0.0,
           "score": {"fakten": 0.0, "quellen_ok": False, "sauber": True, "werkzeug_ok": None}}
    s = evallib.summarize([ok, bad])
    assert s["fragen"] == 2 and s["bewertet"] == 1 and s["nicht_bewertet_fehler"] == 1
    assert s["fakten_mittel"] == 0.5 and s["werkzeug_ok"] == 1.0 and s["voll_bestanden"] == 0


def test_summarize_werkzeug_none_without_expectations():
    row = {"answer": "x", "dauer_s": 1.0, "score": {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None}}
    assert evallib.summarize([row])["werkzeug_ok"] is None


def test_validate_reports_bad_regex_and_duplicates():
    rows = [{**Q, "must_contain": ["("]}, {**Q}]
    problems = evallib.validate_questions(rows)
    assert any("q1" in p and "(" in p for p in problems)
    assert any("doppelt" in p for p in problems)


def test_validate_agent_false_needs_retrieval_and_mode_known():
    rows = [{**Q, "id": "a", "agent": False}, {**Q, "id": "b", "retrieval": {"mode": "magic", "query": "x"}}]
    problems = evallib.validate_questions(rows)
    assert any(p.startswith("a:") and "retrieval" in p for p in problems)
    assert any("magic" in p for p in problems)


def test_compare_lists_deltas():
    rows = evallib.compare({"fakten_mittel": 0.9, "sauber": 1.0}, {"fakten_mittel": 0.8, "sauber": 1.0})
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
