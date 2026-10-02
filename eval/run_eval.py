"""Agentenlauf: jede Frage an den Chat-Agenten eines laufenden Stromlauf-AI-Backends. Kostet API-Tokens je Frage.

Aufruf:  python eval/run_eval.py [--api http://localhost:8010] [--only festo] [--limit 5] [--min 0.8]
                                 [--baseline eval/results/<datei>.json] [--resume eval/results/<datei>.json]

Jede Frage in eval/questions.jsonl (ohne "agent": false) wird als neuer Chat an /api/chat geschickt (nur die
angegebene Wissensquelle). Bewertet wird ohne LLM-Richter, nur mit Regeln (eval/evallib.py):

  fakten     Anteil der must_contain-Muster (Regex, Gross/Klein egal), die in der Antwort vorkommen
  quellen    alle expect_sources-Dateien wurden als Quelle zitiert
  zitate     Anteil der Belege [[Datei|Ort]], die der Zitat-Resolver des Backends bestaetigt (meta-Event)
  teile      referenzierte Bauteile gegen expect_tags/ok_tags der Frage: Recall und Praezision (meta-Event)
  sauber     kein must_not_contain-Muster in der Antwort (Halluzinations-Fallen)
  werkzeug   die in "tools" erwarteten Werkzeuge wurden aufgerufen (nur wenn erwartet)

Ergebnis: eval/results/<zeitstempel>.json plus Tabelle auf der Konsole, nach jeder Frage geschrieben, damit
ein Abbruch keine bezahlten Antworten kostet; --resume setzt eine solche Datei fort (fehlerhafte Fragen werden
wiederholt). --baseline zeigt die Differenz zu einem frueheren Lauf, --min liefert Exit-Code 1 unter dem
Fakten-Mittel. Kostenlose Vorstufe: run_retrieval.py, kostenlose Wiederbewertung: rescore.py.

Tokens und Kosten je Frage stehen im Ergebnis (usage-Ereignisse des Chats, Preise aus app/flow/pricing.py).
Mit Langfuse-Schluesseln in der .env bekommt jede Frage die Tags eval:<lauf> und q:<id>; nach dem Lauf werden
die Bewertungen als Scores an die Session des jeweiligen Chats geschrieben.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# Das Backend neben diesem Skript, nicht das in der venv installierte (ein Worktree hat sonst den Stand des
# Haupt-Checkouts: andere Preistabelle, andere cost_usd-Signatur)
sys.path.insert(0, str(HERE.parent / "backend"))

import evallib  # noqa: E402

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

try:  # Preistabelle und Langfuse-Zugang kommen aus dem Backend
    from app.flow.pricing import cost_usd
    from app.tracing import langfuse_client
except ImportError:  # pragma: no cover
    sys.exit("Backend nicht installiert: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

QUESTIONS = HERE / "questions.jsonl"
RESULTS = HERE / "results"

def _auth_headers() -> dict[str, str]:
    """API_KEY des Backends aus STROMLAUF_API_KEY (leer = Backend offen)."""
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def chat_body(message: str, source_ids: list[str], tags: list[str], model: str | None) -> dict:
    """Anfrage an /api/chat; mit --model faehrt der Lauf ein anderes Modell (Provider) und taggt es in Langfuse."""
    body = {"message": message, "source_ids": source_ids, "trace_tags": list(tags)}
    if model:
        body["model"] = model
        body["trace_tags"].append(f"model:{model}")
    return body


def ask(
    client: httpx.Client, message: str, source_ids: list[str], tags: list[str], model: str | None = None
) -> tuple[str, list[dict], list[str], float, dict]:
    """Eine Frage stellen: (Antwort, Quellen, Werkzeuge, Sekunden, Lauf-Infos mit Verbrauch und Kosten)."""
    started = time.time()
    body = chat_body(message, source_ids, tags, model)
    with client.stream("POST", "/api/chat", json=body) as response:
        response.raise_for_status()
        answer, sources, tools, meta = evallib.parse_sse(response.iter_lines())
    usage = meta["usage"]
    usage["cost_usd"] = usage_cost(usage)
    return answer, sources, tools, time.time() - started, meta


def output_path(requested: Path | None, run: str) -> Path:
    """Ergebnisdatei: Wunsch aus --out (parallele Laeufe je Modell), sonst eval/results/<lauf>.json."""
    return requested if requested else RESULTS / f"{run}.json"


def usage_cost(usage: dict) -> float:
    """Kosten des summierten Verbrauchs einer Frage; Cache-Treffer und -Schreiben zaehlen wie in app/flow/pricing.py."""
    return cost_usd(
        usage["model"],
        usage["input_tokens"],
        usage["output_tokens"],
        usage.get("cache_read_tokens", 0),
        usage.get("cache_creation_tokens", 0),
    )


def push_scores(run: str, rows: list[dict]) -> None:
    """Bewertungen als Scores an die Session des jeweiligen Chats. Ohne Langfuse-Schluessel: nichts."""
    client = langfuse_client()
    if client is None:
        return
    written = 0
    for row in rows:
        session = row.get("conversation_id")
        if not session or evallib.is_error(row):
            continue
        score = row["score"]
        client.create_score(session_id=session, name="fakten", value=score["fakten"], data_type="NUMERIC")
        client.create_score(session_id=session, name="quellen_ok", value=float(score["quellen_ok"]), data_type="NUMERIC")
        client.create_score(session_id=session, name="sauber", value=float(score["sauber"]), data_type="NUMERIC")
        for key in ("zitate_gueltig", "teile_praezision", "teile_recall"):
            if score.get(key) is not None:
                client.create_score(session_id=session, name=key, value=score[key], data_type="NUMERIC")
        written += 1
    client.flush()
    print(f"Langfuse: {written} von {len(rows)} Antworten bewertet (Lauf {run}).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--only", help="Filter auf id oder Quellname, z. B. festo")
    parser.add_argument("--limit", type=int, help="Nur die ersten N Fragen (nach Filter)")
    parser.add_argument("--min", type=float, default=0.0, help="Exit-Code 1, wenn fakten_mittel darunter liegt")
    parser.add_argument("--min-citations", type=float, help="Exit-Code 1, wenn zitate_gueltig darunter liegt oder fehlt")
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    parser.add_argument("--resume", type=Path, help="Abgebrochenen Lauf fortsetzen (Ergebnisdatei)")
    parser.add_argument("--max-cost", type=float, default=0.0, help="Kostendeckel in USD: keine weitere Frage, sobald die Summe darueber liegt")
    parser.add_argument("--model", help="Modell fuer diesen Lauf, z. B. openai:gpt-5-mini oder claude-sonnet-5 (leer = CHAT_MODEL des Backends)")
    parser.add_argument("--out", type=Path, help="Ergebnisdatei (Standard: eval/results/<lauf>.json); nicht mit --resume")
    args = parser.parse_args()
    if args.out and args.resume:
        sys.exit("--out und --resume schliessen sich aus: fortgesetzt wird in die Datei von --resume.")

    questions = [q for q in evallib.load_questions(QUESTIONS, args.only) if q.get("agent", True)]
    if args.limit:
        questions = questions[: args.limit]
    if not questions:
        sys.exit("Keine Fragen ausgewaehlt.")

    run = evallib.run_id()
    rows: list[dict] = []
    if args.resume:
        if not args.resume.exists():
            sys.exit(f"{args.resume} gibt es nicht.")
        if args.resume.stem.startswith("referenz"):
            sys.exit("Referenzlauf wird nicht ueberschrieben. Erst kopieren, dann die Kopie fortsetzen.")
        run = args.resume.stem  # fortgesetzt wird in dieselbe Datei
        rows = [r for r in json.loads(args.resume.read_text(encoding="utf-8"))["results"] if not evallib.is_error(r)]
        done = {r["id"] for r in rows}
        questions = [q for q in questions if q["id"] not in done]
        print(f"Setze {args.resume.name} fort: {len(rows)} fertig, {len(questions)} offen")
        if not questions:
            sys.exit("Alle Fragen dieses Laufs sind schon beantwortet.")
    out = output_path(args.out, run)

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

        spent = 0.0
        for i, q in enumerate(questions, 1):
            if args.max_cost > 0 and spent >= args.max_cost:
                print(f"Kostendeckel erreicht ({spent:.2f} USD >= {args.max_cost:.2f}): {len(questions) - i + 1} Fragen ausgelassen")
                break
            tags = [f"eval:{run}", f"q:{q['id']}"]
            meta: dict = {}
            try:
                answer, cited, tools, seconds, meta = ask(client, q["question"], [by_name[q["source"]]], tags, args.model)
            except Exception as exc:  # Netz, Timeout
                answer, cited, tools, seconds = f"{evallib.ERROR_PREFIX} {type(exc).__name__}: {exc}", [], [], 0.0
            answer_meta = meta.get("answer_meta") or {}
            kept_meta = {k: answer_meta[k] for k in ("referenced_tags", "citation_checks", "citations_valid") if k in answer_meta}
            result = evallib.score(q, answer, cited, tools, meta=kept_meta)
            rows.append({"id": q["id"], "source": q["source"], "question": q["question"], "answer": answer,
                         "sources": cited, "tools": tools, "dauer_s": round(seconds, 1), "score": result,
                         "conversation_id": meta.get("conversation_id", ""), "usage": meta.get("usage", {}),
                         "meta": kept_meta})
            spent += float((meta.get("usage") or {}).get("cost_usd") or 0.0)
            evallib.print_row(i, len(questions), q, result, seconds)
            evallib.save_result(out, evallib.summarize(rows), rows)  # Abbruch kostet keine bezahlte Antwort

    summary = evallib.summarize(rows)
    evallib.save_result(out, summary, rows)
    evallib.print_summary(summary, args.baseline)
    push_scores(run, rows)
    print(f"\nErgebnis: {out}")
    if summary["fakten_mittel"] < args.min:
        print(f"Unter Schwelle {args.min}: fakten_mittel {summary['fakten_mittel']}")
        return 1
    if evallib.below_threshold(summary, args.min_citations):
        print(f"Unter Schwelle {args.min_citations}: zitate_gueltig {summary.get('zitate_gueltig')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
