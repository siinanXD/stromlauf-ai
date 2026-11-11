"""Retrieval-Lauf: kostenlos und deterministisch. Prueft, ob die Werkzeuge die richtigen Belege liefern.

Aufruf:  python eval/run_retrieval.py [--api http://localhost:8010] [--only ur01] [--min 0.9]
                                      [--baseline eval/results/referenz_retrieval_<datum>.json]
                                      [--fusion vector|fulltext|hybrid]

Jede Frage in eval/questions.jsonl mit "retrieval": {"mode", "query"} ruft den passenden Endpunkt auf:

  tag | semantic | keyword   GET /api/search?mode=...&q=...&source_id=...
  fact                       GET /api/facts?tag=...&source_ids=...
  signal                     GET /api/signal-path?tag=...&source_id=...

Die Antwort wird zu Text plus zitierten Dateinamen und mit denselben Regeln bewertet wie eine Agentenantwort
(fakten, quellen, sauber). Bei signal gibt es keine Dateinamen; quellen gilt dort als erfuellt.
Fuer semantic-Fragen mit expect_sources steht dazu Recall@10: Anteil der erwarteten Dateien unter den ersten 10
Treffern (eigene Anfrage mit k=10; die Bewertung bleibt bei k=8). --fusion laesst die Suche nur eine Rangliste nutzen.
Kein Modellaufruf, keine API-Kosten. Ergebnis: eval/results/retrieval_<zeitstempel>.json.
"""

import argparse
import os
import sys
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
FUSIONS = ("hybrid", "vector", "fulltext")  # wie app/retrieval.py
RECALL_K = 10

def _auth_headers() -> dict[str, str]:
    """API_KEY des Backends aus STROMLAUF_API_KEY (leer = Backend offen)."""
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def answer_for_error(exc: Exception) -> str:
    """HTTP-Fehler (404 Kennzeichen unbekannt) und unbrauchbare Antworten (ValueError) sind
    Retrieval-Fehler und werden bewertet (fakten 0); nur Netzfehler bleiben unbewertet."""
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        return f"Kein Ergebnis ({exc.response.status_code}): {detail}"
    if isinstance(exc, ValueError):
        return f"Kein Ergebnis: {exc}"
    return f"{evallib.ERROR_PREFIX} {type(exc).__name__}: {exc}"


def gate_failed(summary: dict, minimum: float) -> bool:
    """--min: unter dem Fakten-Mittel oder mit unbewerteten Fehlern, sobald eine Schwelle gesetzt ist."""
    if minimum <= 0:
        return False
    return summary["fakten_mittel"] < minimum or summary["nicht_bewertet_fehler"] > 0


def recall_at_k(expected: list[str], files: list[str]) -> float | None:
    """Anteil der erwarteten Dateien unter den gelieferten; None, wenn die Frage keine erwartet."""
    return len(set(expected) & set(files)) / len(set(expected)) if expected else None


def recall_summary(rows: list[dict]) -> dict:
    values = [r["recall_at_10"] for r in rows if r.get("recall_at_10") is not None]
    mean = round(sum(values) / len(values), 3) if values else None
    return {"recall_at_10": mean, "recall_at_10_fragen": len(values)}


def fetch(
    client: httpx.Client, question: dict, source_ids: dict[str, str], fusion: str = "hybrid", k: int = 8
) -> object:
    mode, query = question["retrieval"]["mode"], question["retrieval"]["query"]
    source_id = source_ids.get(question.get("source") or "")
    if mode in {"tag", "semantic", "keyword"}:
        params = {"q": query, "mode": mode, "source_id": source_id, "k": k, "fusion": fusion}
        response = client.get("/api/search", params=params)
    elif mode == "fact":
        response = client.get("/api/facts", params={"tag": query, "source_ids": [source_id]})
    elif mode == "signal":
        response = client.get("/api/signal-path", params={"tag": query, "source_id": source_id})
    else:
        raise ValueError(f"Retrieval-Modus {mode!r} unbekannt")
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--only", help="Filter auf id oder Quellname, z. B. ur01")
    parser.add_argument("--min", type=float, default=0.0, help="Exit-Code 1, wenn fakten_mittel darunter liegt")
    parser.add_argument("--min-sources", type=float, default=0.0, help="Exit-Code 1, wenn quellen_ok darunter liegt")
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    parser.add_argument("--fusion", choices=FUSIONS, default="hybrid",
                        help="Ranglisten der Suche mode=semantic: beide (Standard) oder nur Vektor bzw. Volltext")
    args = parser.parse_args()

    questions = [q for q in evallib.load_questions(QUESTIONS, args.only) if q.get("retrieval")]
    if not questions:
        sys.exit("Keine Fragen mit retrieval ausgewaehlt.")

    with httpx.Client(base_url=args.api, timeout=120, headers=_auth_headers()) as client:
        try:
            sources = client.get("/api/sources").raise_for_status().json()
        except httpx.HTTPError as exc:
            sys.exit(f"Backend unter {args.api} nicht erreichbar: {exc}")
        by_name = {s["name"]: s["id"] for s in sources}
        missing = sorted({q["source"] for q in questions if q.get("source")} - set(by_name))
        if missing:
            sys.exit(f"Wissensquellen fehlen im Backend: {missing}. Erst laden (scripts/load_example.py, "
                     "scripts/load_folder.py, scripts/load_testwerk.py --docs).")

        rows = []
        for i, q in enumerate(questions, 1):
            mode = q["retrieval"]["mode"]
            recall = None
            try:
                text, files = evallib.flatten(mode, fetch(client, q, by_name, args.fusion))
                if mode == "semantic" and q.get("expect_sources"):
                    top = evallib.flatten(mode, fetch(client, q, by_name, args.fusion, RECALL_K))[1]
                    recall = recall_at_k(q["expect_sources"], top)
            except Exception as exc:  # HTTP-Fehler, Netz
                text, files = answer_for_error(exc), []
            cited = [{"filename": f} for f in files]
            result = evallib.score(q, text, cited, None, check_sources=mode not in evallib.NO_FILES)
            rows.append({"id": q["id"], "source": q.get("source"), "question": q["question"], "mode": mode,
                         "answer": text, "sources": cited, "dauer_s": 0.0, "score": result,
                         "recall_at_10": recall})
            evallib.print_row(i, len(questions), q, result)

    summary = {**evallib.summarize(rows), "fusion": args.fusion, **recall_summary(rows)}
    out = evallib.write_result(RESULTS, "retrieval_", summary, rows)
    evallib.print_summary(summary, args.baseline)
    print(f"\nErgebnis: {out}")
    if gate_failed(summary, args.min):
        print(f"Unter Schwelle {args.min}: fakten_mittel {summary['fakten_mittel']}, "
              f"unbewertete Fehler {summary['nicht_bewertet_fehler']}")
        return 1
    if args.min_sources > 0 and summary["quellen_ok"] < args.min_sources:
        print(f"Unter Schwelle {args.min_sources}: quellen_ok {summary['quellen_ok']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
