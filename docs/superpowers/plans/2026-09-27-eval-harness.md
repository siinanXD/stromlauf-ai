# Eval-Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kostenlose Retrieval-Bewertung, Wiederbewertung gespeicherter Agentenläufe und Fragen für UR-01, PM1-AR und Testwerk auf dem vorhandenen `eval/`.

**Architecture:** Gemeinsame reine Logik in `eval/evallib.py`; drei dünne Skripte (`run_eval.py` bestehend, `run_retrieval.py` und `rescore.py` neu). Eine Fragenliste `eval/questions.jsonl` mit optionalen Feldern `retrieval`, `tools`, `agent`.

**Tech Stack:** Python 3.11, httpx (im Backend-venv), pytest via `importlib` wie `backend/tests/test_load_testwerk.py`.

**Spec:** `docs/superpowers/specs/2026-09-27-eval-harness-design.md`

## Global Constraints

- Kein LLM-Aufruf in Code, Tests oder Verifikation ohne Rückfrage; `run_eval.py` nicht starten.
- Ausgabe der Skripte deutsch, Kennzahlnamen wie bisher (`fakten_mittel`, `quellen_ok`, `sauber`, `voll_bestanden`, `dauer_mittel_s`), neu `werkzeug_ok`.
- Bewertung deterministisch: gleiche Eingabe, gleiche Punkte.
- ruff: `cd backend && .venv/Scripts/ruff check app tests ../eval ../scripts/...`.
- Tests laufen aus `backend/`: `.venv/Scripts/python -m pytest -q tests/test_eval.py`.

## Review Focus

1. `retrieval.query` als Objekt (calc) mit unbekanntem Artikelcode → Fehlerzeile `[FEHLER]`, kein Abbruch des Laufs (Task 2, `test_run_retrieval_unknown_article`).
2. Ergebnisdatei ohne `tools`-Feld (Referenzlauf 2026-09-26 hat `tools`, ältere evtl. nicht) → `rescore` bewertet `werkzeug_ok` als `null` (Task 3, `test_rescore_without_tools`).
3. `must_contain` mit ungültiger Regex → Validierung meldet ID und Muster statt Traceback (Task 1, `test_validate_reports_bad_regex`).
4. Antwort, die mit `[FEHLER]` beginnt → nicht bewertet, in `nicht_bewertet_fehler` gezählt (Task 1, `test_summarize_separates_errors`).
5. `site`-Anfrage auf eine Halle, die es nicht gibt → Text leer, Fakten 0, kein Traceback (Task 2, `test_flatten_site_unknown_hall`).

---

### Task 1: `eval/evallib.py` — gemeinsame Logik, `run_eval.py` darauf umgestellt

**Files:**
- Create: `eval/evallib.py`
- Modify: `eval/run_eval.py`
- Test: `backend/tests/test_eval.py`

**Interfaces:**
- Produces:
  - `RETRIEVAL_MODES = ("tag", "semantic", "keyword", "fact", "signal", "calc", "site")`
  - `load_questions(path: Path, only: str | None = None) -> list[dict]` (validiert, wirft `ValueError` mit allen Problemen)
  - `validate_questions(rows: list[dict]) -> list[str]`
  - `parse_sse(lines: Iterable[str]) -> tuple[str, list[dict], list[str]]` (Antwort, Quellen, Werkzeuge; `error`-Event → `"\n[FEHLER] ..."` angehängt; `done` beendet)
  - `score(question: dict, answer: str, sources: list[dict], tools: list[str] | None = None, check_sources: bool = True) -> dict` mit Schlüsseln `fakten, fakten_fehlend, quellen_ok, quellen_fehlend, sauber, verboten_gefunden, werkzeug_ok` (`None` wenn `question` keine `tools` hat oder `tools is None`)
  - `passed(result: dict) -> bool` (fakten 1.0, quellen_ok, sauber, werkzeug_ok nicht False)
  - `summarize(rows: list[dict]) -> dict` (bisherige Schlüssel + `werkzeug_ok`: Anteil unter den Fragen mit Erwartung, `None` wenn keine)
  - `compare(summary: dict, baseline: dict) -> list[tuple[str, object, object, float]]`
  - `write_result(results_dir: Path, prefix: str, summary: dict, rows: list[dict]) -> Path` (`<prefix><YYYY-MM-DD_HH-MM-SS>.json`)
  - `print_row(index, total, question, result, seconds)` und `print_summary(summary, baseline_path)` für die Konsolenausgabe

- [ ] **Step 1: Failing tests**

```python
# backend/tests/test_eval.py
import importlib.util, json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("evallib", ROOT / "eval" / "evallib.py")
evallib = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(evallib)

Q = {"id": "q1", "source": "S", "question": "?", "must_contain": ["-K3", "Blatt 4|S\\. 4"],
     "must_not_contain": ["Diagnoseadresse [0-9]{3,}"], "expect_sources": ["a.pdf"], "tools": ["find_tag"]}

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

def test_parse_sse_collects_answer_sources_tools_and_error():
    lines = ["event: conversation", 'data: {"id": "c"}', "", "event: tool_start", 'data: {"name": "find_tag", "args": {}}', "",
             "event: token", 'data: {"text": "Hallo "}', "", "event: sources", 'data: [{"filename": "a.pdf"}]', "",
             "event: token", 'data: {"text": "Welt"}', "", "event: error", 'data: {"message": "kaputt"}', "", "event: done", "data: {}", "",
             "event: token", 'data: {"text": "danach"}', ""]
    answer, sources, tools = evallib.parse_sse(lines)
    assert answer == "Hallo Welt\n[FEHLER] kaputt" and sources == [{"filename": "a.pdf"}] and tools == ["find_tag"]

def test_summarize_separates_errors():
    ok = {"answer": "x", "dauer_s": 2.0, "score": {"fakten": 0.5, "quellen_ok": True, "sauber": True, "werkzeug_ok": True}}
    bad = {"answer": "[FEHLER] Timeout", "dauer_s": 0.0, "score": {"fakten": 0.0, "quellen_ok": False, "sauber": True, "werkzeug_ok": None}}
    s = evallib.summarize([ok, bad])
    assert s["fragen"] == 2 and s["bewertet"] == 1 and s["nicht_bewertet_fehler"] == 1
    assert s["fakten_mittel"] == 0.5 and s["werkzeug_ok"] == 1.0 and s["voll_bestanden"] == 0

def test_summarize_werkzeug_none_without_expectations():
    row = {"answer": "x", "dauer_s": 1.0, "score": {"fakten": 1.0, "quellen_ok": True, "sauber": True, "werkzeug_ok": None}}
    assert evallib.summarize([row])["werkzeug_ok"] is None

def test_validate_reports_bad_regex_and_duplicates():
    rows = [{**Q, "must_contain": ["("]}, {**Q}]
    problems = evallib.validate_questions(rows)
    assert any("q1" in p and "(" in p for p in problems) and any("doppelt" in p for p in problems)

def test_validate_agent_false_needs_retrieval_and_mode_known():
    rows = [{**Q, "id": "a", "agent": False}, {**Q, "id": "b", "retrieval": {"mode": "magic", "query": "x"}}]
    problems = evallib.validate_questions(rows)
    assert any("a" in p and "retrieval" in p for p in problems) and any("magic" in p for p in problems)

def test_compare_lists_deltas():
    rows = evallib.compare({"fakten_mittel": 0.9, "sauber": 1.0}, {"fakten_mittel": 0.8, "sauber": 1.0})
    assert ("fakten_mittel", 0.8, 0.9, 0.1) in [(k, a, b, round(d, 3)) for k, a, b, d in rows]

def test_write_result_names_file(tmp_path):
    out = evallib.write_result(tmp_path, "retrieval_", {"a": 1}, [])
    assert out.name.startswith("retrieval_") and json.loads(out.read_text(encoding="utf-8"))["summary"] == {"a": 1}

def test_questions_file_is_valid():
    rows = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    assert len(rows) >= 24
```

- [ ] **Step 2: Run** `cd backend && .venv/Scripts/python -m pytest -q tests/test_eval.py`
Expected: FAIL, `FileNotFoundError`/`AttributeError` (evallib fehlt).

- [ ] **Step 3: Implement `eval/evallib.py`** with the Interfaces above. `score` keeps the regex semantics of the current `run_eval.score` (IGNORECASE); `werkzeug_ok = None if tools is None or not question.get("tools") else all(t in tools for t in question["tools"])`. `summarize` = current `summarize` plus `werkzeug_ok` (mean over rows whose score has a bool). `validate_questions` checks: id unique, `question` and `source` non-empty when `agent` is not False, every pattern in `must_contain`/`must_not_contain` compiles (`re.error` → `"<id>: Muster <p!r> ungültig: <err>"`), `retrieval.mode in RETRIEVAL_MODES`, `agent: false` requires `retrieval`.

- [ ] **Step 4: Modify `eval/run_eval.py`**: import `evallib` (via `sys.path.insert(0, str(HERE))`), delete the local `load_questions/ask-parsing/score/summarize`, use `parse_sse`, `score(..., tools)`, `summarize`, `write_result(RESULTS, "", ...)`, `print_row`, `print_summary`, `compare`. Add `--limit N` (first N questions after filter) and `--min FLOAT` (exit 1 when `fakten_mittel < min`). Skip questions with `agent: false`. Keep console format.

- [ ] **Step 5: Run** the test file and `ruff check ../eval`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit** `feat(eval): gemeinsame Bewertungslogik in evallib, Werkzeug-Kennzahl, --limit/--min`

### Task 2: Retrieval-Schicht `eval/run_retrieval.py`

**Files:**
- Modify: `eval/evallib.py` (add `flatten`)
- Create: `eval/run_retrieval.py`
- Test: `backend/tests/test_eval.py`

**Interfaces:**
- Consumes: Task 1 functions.
- Produces:
  - `evallib.flatten(mode: str, payload: object) -> tuple[str, list[str]]` — Text und zitierte Dateinamen:
    - `tag|semantic|keyword`: `payload["text"]`, Dateinamen aus `payload["refs"][*]["filename"]`
    - `fact`: Zeilen `"<title>"`, `"<bom_line>"`, je Row `"<label>: <text>, <text>"`; Dateinamen aus `values[*].filename`
    - `signal`: je Node `"<id> | <label> | <ref>"` plus `detail`; Dateinamen `[]`
    - `calc`: `json.dumps(payload, ensure_ascii=False)` (Standard-Trennzeichen `", "` / `": "`); `[]`
    - `site`: `payload` ist die gefundene Halle (dict) oder `None` → `""`; `json.dumps`; `[]`
  - `run_retrieval.fetch(client, question, source_ids: dict[str, str], articles: dict[str, str]) -> object` — ruft den Endpunkt; für `site` sucht es die Halle per `name`-Teilstring (case-insensitive); für `calc` ersetzt es `positions[*].article` (Code) durch `article_id`, unbekannter Code → `ValueError("Artikel X unbekannt")`.
  - Skript: `python eval/run_retrieval.py [--api] [--only] [--min] [--baseline]`; Zeilen wie `run_eval` mit `"mode"` statt `"tools"`, Datei `results/retrieval_<ts>.json`; Fragen ohne `retrieval` übersprungen; Fehler je Frage als `[FEHLER]`-Antwort.

- [ ] **Step 1: Failing tests** (append to `test_eval.py`)

```python
def test_flatten_search_uses_text_and_ref_filenames():
    text, files = evallib.flatten("tag", {"text": "Fundstellen", "refs": [{"filename": "a.pdf"}, {"filename": "a.pdf"}, {"filename": "b.csv"}]})
    assert text == "Fundstellen" and files == ["a.pdf", "b.csv"]

def test_flatten_fact_card_lines_and_files():
    card = {"tag": "-M1", "title": "Motor", "bom_line": "-M1 | Motor", "rows": [
        {"label": "Klemmen", "values": [{"text": "-X4:U", "ref": "-X4:U", "filename": "03.csv"}, {"text": "-X4:V", "ref": "", "filename": "03.csv"}]}]}
    text, files = evallib.flatten("fact", card)
    assert "Klemmen: -X4:U, -X4:V" in text and "Motor" in text and files == ["03.csv"]

def test_flatten_signal_lists_nodes():
    text, files = evallib.flatten("signal", {"start": "-S1", "nodes": [{"id": "FB 10/NW1", "label": "Selbsthaltung", "ref": "FB 10 NW 1", "detail": "U #Start"}], "edges": []})
    assert "FB 10/NW1 | Selbsthaltung | FB 10 NW 1" in text and "U #Start" in text and files == []

def test_flatten_calc_and_site_dump_json():
    assert '"pallets": 160' in evallib.flatten("calc", {"summary": {"pallets": 160}})[0]
    assert evallib.flatten("site", None) == ("", [])
    assert '"docks": 8' in evallib.flatten("site", {"name": "Lager", "docks": 8})[0]

def test_flatten_site_unknown_hall():
    _spec2 = importlib.util.spec_from_file_location("run_retrieval", ROOT / "eval" / "run_retrieval.py")
    rr = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(rr)
    assert rr.find_hall({"halls": [{"name": "Verarbeitung"}]}, "Lager") is None
    assert rr.find_hall({"halls": [{"name": "Lager & Versand"}]}, "lager")["name"] == "Lager & Versand"

def test_run_retrieval_unknown_article():
    _spec2 = importlib.util.spec_from_file_location("run_retrieval", ROOT / "eval" / "run_retrieval.py")
    rr = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(rr)
    with pytest.raises(ValueError, match="XX-1"):
        rr.calc_body({"positions": [{"article": "XX-1", "quantity": 1, "unit": "unit"}]}, {"TP-1": "id1"})
    body = rr.calc_body({"received_at": "2026-09-28T07:00", "positions": [{"article": "TP-1", "quantity": 2, "unit": "pallet"}]}, {"TP-1": "id1"})
    assert body["positions"] == [{"article_id": "id1", "quantity": 2, "unit": "pallet"}] and body["received_at"] == "2026-09-28T07:00"
```

- [ ] **Step 2: Run** → FAIL (`flatten`, `run_retrieval.py` fehlen).
- [ ] **Step 3: Implement** `flatten` in `evallib.py`; `run_retrieval.py` with `find_hall(site: dict, query: str) -> dict | None`, `calc_body(query: dict, articles: dict[str, str]) -> dict`, `fetch(...)`, `main()`. The main loop catches `Exception` per question → answer `"[FEHLER] <Typ>: <msg>"`. `check_sources = mode not in {"signal", "calc", "site"}`.
- [ ] **Step 4: Run** tests + ruff → PASS.
- [ ] **Step 5: Commit** `feat(eval): kostenlose Retrieval-Schicht run_retrieval.py`

### Task 3: Wiederbewertung `eval/rescore.py`

**Files:**
- Create: `eval/rescore.py`
- Test: `backend/tests/test_eval.py`

**Interfaces:**
- Consumes: `evallib.load_questions`, `score`, `summarize`, `compare`, `print_summary`.
- Produces: `rescore.rescore(run: dict, questions: list[dict]) -> tuple[dict, list[dict], list[str]]` (summary, rows with new `score`, IDs im Lauf ohne Frage); CLI `python eval/rescore.py <datei.json> [--questions PATH] [--baseline PATH] [--out PATH]`.

- [ ] **Step 1: Failing tests**

```python
def _rescore_module():
    s = importlib.util.spec_from_file_location("rescore", ROOT / "eval" / "rescore.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def test_rescore_reproduces_reference_run():
    rescore = _rescore_module()
    run = json.loads((ROOT / "eval" / "results" / "referenz_2026-09-26.json").read_text(encoding="utf-8"))
    questions = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    summary, rows, unknown = rescore.rescore(run, questions)
    assert unknown == [] and summary["bewertet"] == run["summary"].get("bewertet", 24) - 0
    for old, new in zip(run["results"], rows, strict=True):
        assert new["score"]["fakten"] == old["score"]["fakten"] and new["score"]["sauber"] == old["score"]["sauber"]

def test_rescore_without_tools():
    rescore = _rescore_module()
    run = {"results": [{"id": "q1", "answer": "-K3 Blatt 4", "sources": [{"filename": "a.pdf"}], "dauer_s": 1.0}]}
    summary, rows, unknown = rescore.rescore(run, [Q])
    assert rows[0]["score"]["werkzeug_ok"] is None and summary["werkzeug_ok"] is None

def test_rescore_counts_unknown_ids():
    rescore = _rescore_module()
    run = {"results": [{"id": "zz", "answer": "x", "sources": [], "dauer_s": 1.0}]}
    summary, rows, unknown = rescore.rescore(run, [Q])
    assert unknown == ["zz"] and rows == [] and summary["fragen"] == 0
```

Note for the reference-run assertion: the reference file's `summary` has no `bewertet`; use `len(run["results"])` instead of the `.get` expression if it reads better. The invariant is: per-question `fakten` and `sauber` identical to the stored values (must_contain patterns of the 24 existing questions stay unchanged in Task 4).

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `rescore.py`. **Step 4: Run** tests + ruff → PASS.
- [ ] **Step 5: Commit** `feat(eval): rescore.py bewertet gespeicherte Laeufe neu`

### Task 4: Fragen für UR-01, PM1-AR, FB-01-Ergänzungen, Testwerk; `retrieval`/`tools` an bestehenden Fragen

**Files:**
- Modify: `eval/questions.jsonl`
- Test: `backend/tests/test_eval.py` (`test_questions_file_is_valid` erweitert)

**Rules:** must_contain der 24 bestehenden Fragen unverändert (Task 3 Test). Neue Fakten aus `examples/umroller/`, `examples/aufrollung/`, `examples/testwerk/testwerk.json` nachschlagen. Fallen: `ur01-nicht-vorhanden` (Profinet-Name der CPU), `pm1ar-nicht-vorhanden` (Seriennummer -U1).

- [ ] **Step 1: Extend test**

```python
def test_questions_cover_testdoku_and_testwerk():
    rows = evallib.load_questions(ROOT / "eval" / "questions.jsonl")
    by_source = {}
    for r in rows: by_source.setdefault(r["source"], []).append(r)
    assert len(by_source["Umroller UR-01"]) >= 10 and len(by_source["Aufrollung PM1-AR"]) >= 9
    assert len([r for r in rows if r.get("agent") is False]) >= 4
    assert sum(1 for r in rows if r.get("retrieval")) >= 30
    assert all(r["id"].endswith("nicht-vorhanden") for r in rows if not r["expect_sources"] and r.get("agent", True))
```

- [ ] **Step 2: Run** → FAIL (Quellen fehlen). **Step 3: Add lines** (retrieval + tools on existing FB-01 lines; new UR-01/PM1-AR/FB-01/Testwerk lines, source `"Testwerk"` for `agent: false`). **Step 4: Run** tests + `python eval/run_retrieval.py` live (kostenlos) → Mittel ≥ 0,9; tighten patterns against actual retrieval text where a fact is phrased differently, never against agent output. **Step 5: Commit** `feat(eval): Fragen UR-01, PM1-AR, Testwerk; retrieval-Anfragen an bestehenden Fragen`

### Task 5: Doku und Referenzlauf

**Files:**
- Modify: `eval/README.md`, `README.md` (Abschnitt „Antwortqualitaet messen“), `AGENTS.md` (eine Zeile unter Build & Test)
- Add: `eval/results/referenz_retrieval_<datum>.json` (`git add -f`)

- [ ] **Step 1:** README/eval README: three layers, commands, cost note („`run_eval.py` kostet Tokens je Frage; erst `run_retrieval.py`“), Kennzahl `werkzeug_ok`, Fragen ergänzen (neue Felder). Table of sources updated (FB-01, Festo, AWL, UR-01, PM1-AR, Testwerk).
- [ ] **Step 2:** `python eval/run_retrieval.py` → copy result to `referenz_retrieval_2026-09-27.json`, `git add -f`.
- [ ] **Step 3:** Full suite `cd backend && .venv/Scripts/python -m pytest -q` + ruff. **Step 4: Commit** `docs(eval): drei Schichten, Referenz-Retrieval-Lauf`
