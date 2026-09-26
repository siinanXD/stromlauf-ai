"""Wiederbewertung: gespeicherte Agentenantworten mit der aktuellen questions.jsonl neu bewerten. Kostenlos.

Aufruf:  python eval/rescore.py eval/results/<datei>.json [--questions eval/questions.jsonl]
                                [--baseline eval/results/<andere>.json] [--out eval/results/<neu>.json]

Damit lassen sich Muster (must_contain, must_not_contain, expect_sources, tools) nachschaerfen, ohne den
Agenten erneut laufen zu lassen. Fragen, die im Lauf fehlen, werden nicht bewertet; Antworten im Lauf, zu
denen es keine Frage mehr gibt, werden gezaehlt und ausgegeben.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evallib  # noqa: E402

QUESTIONS = HERE / "questions.jsonl"


def rescore(run: dict, questions: list[dict]) -> tuple[dict, list[dict], list[str]]:
    """(Zusammenfassung, Zeilen mit neuer Bewertung, IDs im Lauf ohne Frage)."""
    by_id = {q["id"]: q for q in questions}
    rows, unknown = [], []
    for old in run["results"]:
        question = by_id.get(old["id"])
        if question is None:
            unknown.append(old["id"])
            continue
        result = evallib.score(question, old.get("answer", ""), old.get("sources", []), old.get("tools"))
        rows.append({**old, "question": question["question"], "score": result})
    return evallib.summarize(rows), rows, unknown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run", type=Path, help="Gespeicherter Lauf (JSON aus run_eval.py oder run_retrieval.py)")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    parser.add_argument("--out", type=Path, help="Neu bewerteten Lauf hier speichern")
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="utf-8"))
    summary, rows, unknown = rescore(run, evallib.load_questions(args.questions))
    for i, row in enumerate(rows, 1):
        evallib.print_row(i, len(rows), row, row["score"], row.get("dauer_s"))
    if unknown:
        print(f"\nOhne Frage in {args.questions.name} (nicht bewertet): {unknown}")
    evallib.print_summary(summary, args.baseline)
    if args.out:
        args.out.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\nErgebnis: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
