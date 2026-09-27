"""Agentenlauf: jede Frage an den Chat-Agenten eines laufenden Stromlauf-AI-Backends. Kostet API-Tokens je Frage.

Aufruf:  python eval/run_eval.py [--api http://localhost:8010] [--only festo] [--limit 5] [--min 0.8]
                                 [--baseline eval/results/<datei>.json]

Jede Frage in eval/questions.jsonl (ohne "agent": false) wird als neuer Chat an /api/chat geschickt (nur die
angegebene Wissensquelle). Bewertet wird ohne LLM-Richter, nur mit Regeln (eval/evallib.py):

  fakten     Anteil der must_contain-Muster (Regex, Gross/Klein egal), die in der Antwort vorkommen
  quellen    alle expect_sources-Dateien wurden als Quelle zitiert
  sauber     kein must_not_contain-Muster in der Antwort (Halluzinations-Fallen)
  werkzeug   die in "tools" erwarteten Werkzeuge wurden aufgerufen (nur wenn erwartet)

Ergebnis: eval/results/<zeitstempel>.json plus Tabelle auf der Konsole. --baseline zeigt die Differenz zu
einem frueheren Lauf, --min liefert Exit-Code 1 unter dem Fakten-Mittel. Kostenlose Vorstufe: run_retrieval.py,
kostenlose Wiederbewertung eines gespeicherten Laufs: rescore.py.
"""

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evallib  # noqa: E402

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

QUESTIONS = HERE / "questions.jsonl"
RESULTS = HERE / "results"

def _auth_headers() -> dict[str, str]:
    """API_KEY des Backends aus STROMLAUF_API_KEY (leer = Backend offen)."""
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def ask(client: httpx.Client, message: str, source_ids: list[str]) -> tuple[str, list[dict], list[str], float]:
    """Schickt eine Frage, liest den SSE-Strom, gibt (Antwort, Quellen, Werkzeuge, Sekunden) zurueck."""
    started = time.time()
    with client.stream("POST", "/api/chat", json={"message": message, "source_ids": source_ids}) as response:
        response.raise_for_status()
        answer, sources, tools = evallib.parse_sse(response.iter_lines())
    return answer, sources, tools, time.time() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--only", help="Filter auf id oder Quellname, z. B. festo")
    parser.add_argument("--limit", type=int, help="Nur die ersten N Fragen (nach Filter)")
    parser.add_argument("--min", type=float, default=0.0, help="Exit-Code 1, wenn fakten_mittel darunter liegt")
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    args = parser.parse_args()

    questions = [q for q in evallib.load_questions(QUESTIONS, args.only) if q.get("agent", True)]
    if args.limit:
        questions = questions[: args.limit]
    if not questions:
        sys.exit("Keine Fragen ausgewaehlt.")

    with httpx.Client(base_url=args.api, timeout=600, headers=_auth_headers()) as client:
        try:
            sources = client.get("/api/sources").json()
        except httpx.HTTPError as exc:
            sys.exit(f"Backend unter {args.api} nicht erreichbar: {exc}")
        by_name = {s["name"]: s["id"] for s in sources}
        missing = sorted({q["source"] for q in questions} - set(by_name))
        if missing:
            sys.exit(f"Wissensquellen fehlen im Backend: {missing}. Erst laden (scripts/load_example.py, "
                     "scripts/load_folder.py, scripts/load_testwerk.py --docs).")

        rows = []
        for i, q in enumerate(questions, 1):
            try:
                answer, cited, tools, seconds = ask(client, q["question"], [by_name[q["source"]]])
            except Exception as exc:  # Netz, Timeout
                answer, cited, tools, seconds = f"{evallib.ERROR_PREFIX} {type(exc).__name__}: {exc}", [], [], 0.0
            result = evallib.score(q, answer, cited, tools)
            rows.append({"id": q["id"], "source": q["source"], "question": q["question"], "answer": answer,
                         "sources": cited, "tools": tools, "dauer_s": round(seconds, 1), "score": result})
            evallib.print_row(i, len(questions), q, result, seconds)

    summary = evallib.summarize(rows)
    out = evallib.write_result(RESULTS, "", summary, rows)
    evallib.print_summary(summary, args.baseline)
    print(f"\nErgebnis: {out}")
    if summary["fakten_mittel"] < args.min:
        print(f"Unter Schwelle {args.min}: fakten_mittel {summary['fakten_mittel']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
