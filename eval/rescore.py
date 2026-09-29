"""Wiederbewertung: gespeicherte Agentenantworten mit der aktuellen questions.jsonl neu bewerten. Kostenlos.

Aufruf:  python eval/rescore.py eval/results/<datei>.json [--questions eval/questions.jsonl]
                                [--baseline eval/results/<andere>.json] [--out eval/results/<neu>.json]
                                [--api http://127.0.0.1:8010] [--min-citations 0.9]
                                [--expect-invalid "[[02_Stueckliste_FB-01.xlsx|-X3:3]]" ...]

Damit lassen sich Muster (must_contain, must_not_contain, expect_sources, tools) nachschaerfen, ohne den
Agenten erneut laufen zu lassen. Fragen, die im Lauf fehlen, werden nicht bewertet; Antworten im Lauf, zu
denen es keine Frage mehr gibt, werden gezaehlt und ausgegeben.

Mit --api werden die Belege [[Datei|Ort]] alter Laeufe ohne gespeicherte Belegpruefung vom laufenden Backend
nachgeprueft (POST /api/answers/validate-citations, Zitat-Resolver, kein Modellaufruf); so entsteht
``zitate_gueltig`` auch fuer Referenzlaeufe von vor Issue #46. Die Wissensquellen muessen dort geladen sein.
--min-citations liefert Exit-Code 1 unter der Schwelle (oder ohne Wert), --expect-invalid Exit-Code 1, wenn
ein genannter Beleg nicht als ungueltig erkannt wurde (Regressionstest des Resolvers im CI).
"""

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evallib  # noqa: E402

QUESTIONS = HERE / "questions.jsonl"
Checker = Callable[[dict], dict | None]


def rescore(run: dict, questions: list[dict], checker: Checker | None = None) -> tuple[dict, list[dict], list[str]]:
    """(Zusammenfassung, Zeilen mit neuer Bewertung, IDs im Lauf ohne Frage).

    ``checker`` liefert fuer eine Zeile ohne gespeicherte Belegpruefung (kein ``citation_checks`` im meta)
    das meta-Event nach (siehe --api); das Ergebnis wird in das gespeicherte meta gemischt.
    """
    by_id = {q["id"]: q for q in questions}
    rows, unknown = [], []
    for old in run["results"]:
        question = by_id.get(old["id"])
        if question is None:
            unknown.append(old["id"])
            continue
        meta = old.get("meta")
        if checker is not None and "citation_checks" not in (meta or {}) and not evallib.is_error(old):
            fetched = checker(old)
            if fetched is not None:
                meta = {**(meta or {}), **fetched}
        result = evallib.score(question, old.get("answer", ""), old.get("sources", []), old.get("tools"),
                               check_sources=old.get("mode") not in evallib.NO_FILES, meta=meta)
        row = {**old, "question": question["question"], "score": result}
        if meta is not None:
            row["meta"] = meta
        rows.append(row)
    return evallib.summarize(rows), rows, unknown


def missing_expected(rows: list[dict], markers: list[str]) -> list[str]:
    """Belege, die als ungueltig erwartet wurden, aber in keiner Zeile als ungueltig bewertet sind."""
    flagged = {text for row in rows for text in row.get("score", {}).get("zitate_ungueltig", [])}
    return [m for m in markers if m not in flagged]


def api_checker(api: str, transport=None) -> Checker:
    """Belegpruefung ueber das Backend: Quelle per Name aufloesen, Antwort mit ihren Fundstellen einreichen."""
    import httpx

    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    client = httpx.Client(base_url=api, timeout=120, headers={"X-API-Key": key} if key else {}, transport=transport)
    by_name = {s["name"]: s["id"] for s in client.get("/api/sources").raise_for_status().json()}

    def check(row: dict) -> dict | None:
        source_id = by_name.get(row.get("source", ""))
        if source_id is None or not row.get("answer"):
            return None
        body = {"answer": row["answer"], "source_ids": [source_id],
                "sources": [{"filename": s.get("filename", "")} for s in row.get("sources", [])]}
        return client.post("/api/answers/validate-citations", json=body).raise_for_status().json()

    return check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run", type=Path, help="Gespeicherter Lauf (JSON aus run_eval.py oder run_retrieval.py)")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    parser.add_argument("--out", type=Path, help="Neu bewerteten Lauf hier speichern")
    parser.add_argument("--api", help="Backend, das fehlende Belegpruefungen nachliefert (kein Modellaufruf)")
    parser.add_argument("--min-citations", type=float, help="Exit-Code 1, wenn zitate_gueltig darunter liegt oder fehlt")
    parser.add_argument("--expect-invalid", action="append", default=[], metavar="MARKER",
                        help="Beleg, der als ungueltig erkannt sein muss (mehrfach moeglich); sonst Exit-Code 1")
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="utf-8"))
    checker = api_checker(args.api) if args.api else None
    summary, rows, unknown = rescore(run, evallib.load_questions(args.questions), checker)
    for i, row in enumerate(rows, 1):
        evallib.print_row(i, len(rows), row, row["score"], row.get("dauer_s"))
    if unknown:
        print(f"\nOhne Frage in {args.questions.name} (nicht bewertet): {unknown}")
    evallib.print_summary(summary, args.baseline)
    if args.out:
        args.out.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\nErgebnis: {args.out}")
    status = 0
    if evallib.below_threshold(summary, args.min_citations):
        print(f"Unter Schwelle {args.min_citations}: zitate_gueltig {summary.get('zitate_gueltig')}")
        status = 1
    missing = missing_expected(rows, args.expect_invalid)
    if missing:
        print(f"Nicht als ungueltig erkannt: {missing}")
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
