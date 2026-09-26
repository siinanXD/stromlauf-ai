"""Retrieval-Lauf: kostenlos und deterministisch. Prueft, ob die Werkzeuge die richtigen Belege liefern.

Aufruf:  python eval/run_retrieval.py [--api http://localhost:8010] [--only ur01] [--min 0.9]
                                      [--baseline eval/results/referenz_retrieval_<datum>.json]

Jede Frage in eval/questions.jsonl mit "retrieval": {"mode", "query"} ruft den passenden Endpunkt auf:

  tag | semantic | keyword   GET /api/search?mode=...&q=...&source_id=...
  fact                       GET /api/facts?tag=...&source_ids=...
  signal                     GET /api/signal-path?tag=...&source_id=...
  calc                       POST /api/calc (Artikelcodes werden ueber /api/articles in IDs aufgeloest)
  site                       GET /api/site, Halle per Namensteil

Die Antwort wird zu Text plus zitierten Dateinamen und mit denselben Regeln bewertet wie eine Agentenantwort
(fakten, quellen, sauber). Bei signal, calc und site gibt es keine Dateinamen; quellen gilt dort als erfuellt.
Kein Modellaufruf, keine API-Kosten. Ergebnis: eval/results/retrieval_<zeitstempel>.json.
"""

import argparse
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


def answer_for_error(exc: Exception) -> str:
    """HTTP-Fehler (404 Kennzeichen unbekannt, 409 Testwerk fehlt) und unbekannte Artikel sind Retrieval-Fehler
    und werden bewertet (fakten 0); nur Netzfehler bleiben unbewertet."""
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


def find_hall(site: dict, query: str) -> dict | None:
    needle = query.strip().lower()
    return next((h for h in site.get("halls", []) if needle in h["name"].lower()), None)


def calc_body(query: dict, articles: dict[str, str]) -> dict:
    """Auftrag mit Artikelcodes -> Body fuer /api/calc mit Artikel-IDs."""
    positions = []
    for position in query["positions"]:
        code = position["article"]
        if code not in articles:
            raise ValueError(f"Artikel {code} unbekannt")
        positions.append({"article_id": articles[code], "quantity": position["quantity"], "unit": position["unit"]})
    body = {k: v for k, v in query.items() if k != "positions"}
    body["positions"] = positions
    return body


def fetch(client: httpx.Client, question: dict, source_ids: dict[str, str], articles: dict[str, str]) -> object:
    mode, query = question["retrieval"]["mode"], question["retrieval"]["query"]
    source_id = source_ids.get(question.get("source") or "")
    if mode in {"tag", "semantic", "keyword"}:
        response = client.get("/api/search", params={"q": query, "mode": mode, "source_id": source_id, "k": 8})
    elif mode == "fact":
        response = client.get("/api/facts", params={"tag": query, "source_ids": [source_id]})
    elif mode == "signal":
        response = client.get("/api/signal-path", params={"tag": query, "source_id": source_id})
    elif mode == "calc":
        response = client.post("/api/calc", json=calc_body(query, articles))
    else:
        response = client.get("/api/site")
        response.raise_for_status()
        return find_hall(response.json(), query)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--only", help="Filter auf id oder Quellname, z. B. ur01")
    parser.add_argument("--min", type=float, default=0.0, help="Exit-Code 1, wenn fakten_mittel darunter liegt")
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    args = parser.parse_args()

    questions = [q for q in evallib.load_questions(QUESTIONS, args.only) if q.get("retrieval")]
    if not questions:
        sys.exit("Keine Fragen mit retrieval ausgewaehlt.")

    with httpx.Client(base_url=args.api, timeout=120) as client:
        try:
            sources = client.get("/api/sources").raise_for_status().json()
            articles = {a["code"]: a["id"] for a in client.get("/api/articles").raise_for_status().json()}
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
            try:
                text, files = evallib.flatten(mode, fetch(client, q, by_name, articles))
            except Exception as exc:  # HTTP-Fehler, unbekannter Artikel, Netz
                text, files = answer_for_error(exc), []
            cited = [{"filename": f} for f in files]
            result = evallib.score(q, text, cited, None, check_sources=mode not in evallib.NO_FILES)
            rows.append({"id": q["id"], "source": q.get("source"), "question": q["question"], "mode": mode,
                         "answer": text, "sources": cited, "dauer_s": 0.0, "score": result})
            evallib.print_row(i, len(questions), q, result)

    summary = evallib.summarize(rows)
    out = evallib.write_result(RESULTS, "retrieval_", summary, rows)
    evallib.print_summary(summary, args.baseline)
    print(f"\nErgebnis: {out}")
    if gate_failed(summary, args.min):
        print(f"Unter Schwelle {args.min}: fakten_mittel {summary['fakten_mittel']}, "
              f"unbewertete Fehler {summary['nicht_bewertet_fehler']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
