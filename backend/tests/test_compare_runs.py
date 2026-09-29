"""Provider-Vergleich zweier Agentenlaeufe (eval/compare_runs.py): Zusammenfassung und Fragen nebeneinander."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "eval" / "compare_runs.py"
sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("compare_runs", SCRIPT)
compare_runs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = compare_runs
_spec.loader.exec_module(compare_runs)


def _run(
    model: str, facts: list[float], cost: list[float], seconds: list[float], sources_ok: bool = True
) -> dict:
    rows = []
    for i, (f, c, s) in enumerate(zip(facts, cost, seconds, strict=True), 1):
        rows.append(
            {
                "id": f"q{i}",
                "source": "Foerderband FB-01",
                "question": f"Frage {i}?",
                "answer": "…",
                "sources": [],
                "tools": [],
                "dauer_s": s,
                "score": {
                    "fakten": f,
                    "quellen_ok": sources_ok,
                    "sauber": True,
                    "werkzeug_ok": None,
                },
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 100,
                    "calls": 2,
                    "model": model,
                    "cost_usd": c,
                },
            }
        )
    summary = {
        "fragen": len(rows),
        "bewertet": len(rows),
        "nicht_bewertet_fehler": 0,
        "fakten_mittel": round(sum(facts) / len(facts), 3),
        "quellen_ok": 1.0 if sources_ok else 0.0,
        "sauber": 1.0,
        "werkzeug_ok": None,
        "voll_bestanden": sum(1 for f in facts if f == 1.0 and sources_ok),
        "dauer_mittel_s": round(sum(seconds) / len(seconds), 1),
        "tokens_ein": 1000 * len(rows),
        "tokens_aus": 100 * len(rows),
        "modellaufrufe": 2 * len(rows),
        "kosten_usd": round(sum(cost), 4),
    }
    return {"summary": summary, "results": rows}


CLAUDE = _run("claude-sonnet-5-20260115", [1.0, 1.0, 0.5], [0.04, 0.05, 0.03], [12.0, 15.0, 9.0])
GPT = _run("gpt-5-mini-2025-08-07", [1.0, 0.5, 0.5], [0.004, 0.005, 0.003], [20.0, 18.0, 22.0])


def test_modellname_kommt_aus_den_antworten():
    assert compare_runs.model_of(CLAUDE) == "claude-sonnet-5-20260115"
    assert compare_runs.model_of({"summary": {}, "results": []}) == "unbekannt"


def test_vergleich_stellt_kennzahlen_und_fragen_nebeneinander():
    comparison = compare_runs.compare(CLAUDE, GPT)
    metrics = {row["kennzahl"]: (row["a"], row["b"]) for row in comparison["kennzahlen"]}
    assert metrics["fakten_mittel"] == (0.833, 0.667)
    assert metrics["quellen_ok"] == (1.0, 1.0)
    assert metrics["kosten_usd"] == (0.12, 0.012)
    assert metrics["kosten_je_antwort_usd"] == (0.04, 0.004)
    assert metrics["dauer_mittel_s"] == (12.0, 20.0)
    assert comparison["modelle"] == ("claude-sonnet-5-20260115", "gpt-5-mini-2025-08-07")
    questions = {row["id"]: row for row in comparison["fragen"]}
    assert questions["q2"]["fakten"] == (1.0, 0.5) and questions["q2"]["kosten_usd"] == (
        0.05,
        0.005,
    )
    assert questions["q2"]["unterschied"] is True and questions["q1"]["unterschied"] is False


def test_zitate_zaehlen_als_kennzahl_und_als_unterschied_je_frage():
    a, b = json.loads(json.dumps(CLAUDE)), json.loads(json.dumps(GPT))
    a["summary"]["zitate_gueltig"], b["summary"]["zitate_gueltig"] = 0.947, 0.907
    a["results"][0]["score"]["zitate_gueltig"], b["results"][0]["score"]["zitate_gueltig"] = (
        1.0,
        0.667,
    )
    comparison = compare_runs.compare(a, b)
    metrics = {row["kennzahl"]: (row["a"], row["b"]) for row in comparison["kennzahlen"]}
    assert metrics["zitate_gueltig"] == (0.947, 0.907)
    questions = {row["id"]: row for row in comparison["fragen"]}
    assert (
        questions["q1"]["zitate_gueltig"] == (1.0, 0.667) and questions["q1"]["unterschied"] is True
    )
    assert "| zitate_gueltig | 0.947 | 0.907 |" in compare_runs.render_markdown(comparison)


def test_markdown_hat_beide_modelle_und_je_frage_eine_zeile():
    text = compare_runs.render_markdown(compare_runs.compare(CLAUDE, GPT))
    assert "claude-sonnet-5-20260115" in text and "gpt-5-mini-2025-08-07" in text
    assert "| fakten_mittel | 0.833 | 0.667 |" in text
    assert text.count("| `q") == 3
    assert "0.0040" in text  # Kosten je Antwort mit vier Nachkommastellen


def test_main_schreibt_markdown_datei(tmp_path: Path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(CLAUDE), encoding="utf-8")
    b.write_text(json.dumps(GPT), encoding="utf-8")
    out = tmp_path / "vergleich.md"
    assert compare_runs.main([str(a), str(b), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Vergleich")
