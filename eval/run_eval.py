"""Deterministischer Eval-Lauf gegen ein laufendes Stromlauf-AI-Backend.

Aufruf:  python eval/run_eval.py [--api http://localhost:8010] [--only festo] [--baseline eval/results/<datei>.json]

Jede Frage in eval/questions.jsonl wird als neuer Chat an /api/chat geschickt (nur die angegebene
Wissensquelle). Bewertet wird ohne LLM-Richter, nur mit Regeln:

  fakten    Anteil der must_contain-Muster (Regex, Gross/Klein egal), die in der Antwort vorkommen
  quellen   alle expect_sources-Dateien wurden als Quelle zitiert
  sauber    kein must_not_contain-Muster in der Antwort (Halluzinations-Fallen)

Ergebnis: eval/results/<zeitstempel>.json plus Tabelle auf der Konsole. Mit --baseline wird die
Differenz zu einem frueheren Lauf angezeigt. Jede Frage kostet API-Tokens (ein Agentenlauf).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

# USD je Million Token (Input, Output), Stand 2026-09, platform.claude.com/docs/en/models/overview
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5": (5.0, 25.0),  # Vorgaenger, Schaetzung
}

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.jsonl"
RESULTS = HERE / "results"


def load_questions(only: str | None) -> list[dict]:
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if only:
        rows = [r for r in rows if only.lower() in r["id"].lower() or only.lower() in r["source"].lower()]
    return rows


def cost_usd(usage: dict) -> float:
    model = usage.get("model") or ""
    prices = next((p for key, p in PRICES.items() if model.startswith(key)), None)
    if not prices:
        return 0.0
    return usage.get("input_tokens", 0) / 1e6 * prices[0] + usage.get("output_tokens", 0) / 1e6 * prices[1]


def ask(
    client: httpx.Client, message: str, source_ids: list[str], tags: list[str] | None = None
) -> tuple[str, list[dict], list[str], float, dict]:
    """Schickt eine Frage, liest den SSE-Stream, gibt (Antwort, Quellen, Toolaufrufe, Sekunden, Usage) zurueck."""
    answer, sources, tools = [], [], []
    usage = {"input_tokens": 0, "output_tokens": 0, "model": "", "calls": 0}
    started = time.time()
    body = {"message": message, "source_ids": source_ids, "trace_tags": tags or []}
    with client.stream("POST", "/api/chat", json=body) as response:
        response.raise_for_status()
        event = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event:
                data = json.loads(line[5:].strip() or "null")
                if event == "token":
                    answer.append(data["text"])
                elif event == "sources":
                    sources = data
                elif event == "tool_start":
                    tools.append(data["name"])
                elif event == "usage":
                    usage["input_tokens"] += data.get("input_tokens", 0)
                    usage["output_tokens"] += data.get("output_tokens", 0)
                    usage["model"] = data.get("model") or usage["model"]
                    usage["calls"] += 1
                elif event == "error":
                    answer.append(f"\n[FEHLER] {data.get('message')}")
                elif event == "done":
                    break
    usage["cost_usd"] = round(cost_usd(usage), 4)
    return "".join(answer), sources, tools, time.time() - started, usage


def score(question: dict, answer: str, sources: list[dict]) -> dict:
    text = answer
    hits = [bool(re.search(p, text, re.IGNORECASE)) for p in question["must_contain"]]
    forbidden = [p for p in question["must_not_contain"] if re.search(p, text, re.IGNORECASE)]
    cited = {s.get("filename", "") for s in sources}
    missing_sources = [f for f in question["expect_sources"] if f not in cited]
    return {
        "fakten": sum(hits) / len(hits) if hits else 1.0,
        "fakten_fehlend": [p for p, h in zip(question["must_contain"], hits) if not h],
        "quellen_ok": not missing_sources,
        "quellen_fehlend": missing_sources,
        "sauber": not forbidden,
        "verboten_gefunden": forbidden,
    }


def summarize(all_rows: list[dict]) -> dict:
    """API-/Netzfehler zaehlen nicht als falsche Antwort, sie werden getrennt ausgewiesen."""
    failed = [r for r in all_rows if r["answer"].startswith("[FEHLER]")]
    rows = [r for r in all_rows if not r["answer"].startswith("[FEHLER]")]
    n = len(rows) or 1
    return {
        "fragen": len(all_rows),
        "bewertet": len(rows),
        "nicht_bewertet_fehler": len(failed),
        "fakten_mittel": round(sum(r["score"]["fakten"] for r in rows) / n, 3),
        "quellen_ok": round(sum(r["score"]["quellen_ok"] for r in rows) / n, 3),
        "sauber": round(sum(r["score"]["sauber"] for r in rows) / n, 3),
        "voll_bestanden": sum(
            r["score"]["fakten"] == 1.0 and r["score"]["quellen_ok"] and r["score"]["sauber"] for r in rows
        ),
        "dauer_mittel_s": round(sum(r["dauer_s"] for r in rows) / n, 1),
        "modell": next((r["usage"]["model"] for r in rows if r.get("usage", {}).get("model")), ""),
        "tokens_input": sum(r.get("usage", {}).get("input_tokens", 0) for r in rows),
        "tokens_output": sum(r.get("usage", {}).get("output_tokens", 0) for r in rows),
        "kosten_usd": round(sum(r.get("usage", {}).get("cost_usd", 0.0) for r in rows), 2),
    }


def push_scores_to_langfuse(run_id: str, rows: list[dict]) -> None:
    """Schreibt fakten/quellen/sauber als Scores an die Traces mit Tag eval:<run_id>. Ohne Keys: nichts."""
    import os

    env_file = HERE.parent / ".env"  # Keys aus der .env des Repos uebernehmen, falls nicht gesetzt
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LANGFUSE_") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return
    try:
        from langfuse import Langfuse
    except ImportError:
        print("Langfuse-Paket fehlt (pip install langfuse), Scores nicht uebertragen.")
        return
    client = Langfuse()
    print("Scores nach Langfuse ...", end="", flush=True)
    written = 0
    for attempt in range(6):  # Ingestion ist asynchron, kurz warten
        traces = client.api.trace.list(tags=[f"eval:{run_id}"], limit=100).data
        by_question = {}
        for trace in traces:
            for tag in trace.tags or []:
                if tag.startswith("q:"):
                    by_question[tag[2:]] = trace.id
        if len(by_question) >= len(rows) or attempt == 5:
            for row in rows:
                trace_id = by_question.get(row["id"])
                if not trace_id:
                    continue
                score = row["score"]
                client.create_score(trace_id=trace_id, name="fakten", value=score["fakten"], data_type="NUMERIC")
                client.create_score(trace_id=trace_id, name="quellen_ok", value=1.0 if score["quellen_ok"] else 0.0)
                client.create_score(trace_id=trace_id, name="sauber", value=1.0 if score["sauber"] else 0.0)
                written += 1
            break
        time.sleep(5)
    client.flush()
    print(f" {written}/{len(rows)} Traces bewertet.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--only", help="Filter auf id oder Quellname, z. B. festo")
    parser.add_argument("--baseline", type=Path, help="Frueheres Ergebnis zum Vergleich")
    parser.add_argument("--resume", type=Path, help="Abgebrochenen Lauf fortsetzen (Ergebnisdatei)")
    args = parser.parse_args()

    questions = load_questions(args.only)
    if not questions:
        sys.exit("Keine Fragen ausgewaehlt.")
    run_id = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    rows: list[dict] = []
    if args.resume and args.resume.exists():
        run_id = args.resume.stem
        rows = [r for r in json.loads(args.resume.read_text(encoding="utf-8"))["results"] if not r["answer"].startswith("[FEHLER]")]
        done = {r["id"] for r in rows}
        questions = [q for q in questions if q["id"] not in done]
        print(f"Setze {args.resume.name} fort: {len(rows)} fertig, {len(questions)} offen")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{run_id}.json"

    def save() -> None:
        out.write_text(json.dumps({"summary": summarize(rows), "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    with httpx.Client(base_url=args.api, timeout=600) as client:
        try:
            sources = client.get("/api/sources").json()
        except httpx.HTTPError as exc:
            sys.exit(f"Backend unter {args.api} nicht erreichbar: {exc}")
        by_name = {s["name"]: s["id"] for s in sources}
        missing = sorted({q["source"] for q in questions} - set(by_name))
        if missing:
            sys.exit(f"Wissensquellen fehlen im Backend: {missing}. Erst laden (scripts/load_example.py, scripts/load_folder.py).")

        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {q['id']}: {q['question'][:70]}", flush=True)
            try:
                answer, cited, tools, seconds, usage = ask(
                    client, q["question"], [by_name[q["source"]]], tags=[f"eval:{run_id}", f"q:{q['id']}"]
                )
            except Exception as exc:  # Netz, Timeout
                answer, cited, tools, seconds, usage = f"[FEHLER] {type(exc).__name__}: {exc}", [], [], 0.0, {}
            result = score(q, answer, cited)
            rows.append({"id": q["id"], "source": q["source"], "question": q["question"], "answer": answer,
                         "sources": cited, "tools": tools, "dauer_s": round(seconds, 1), "usage": usage, "score": result})
            flag = "OK " if result["fakten"] == 1.0 and result["quellen_ok"] and result["sauber"] else "-- "
            print(f"      {flag} fakten {result['fakten']:.2f}  quellen {'ja' if result['quellen_ok'] else 'NEIN'}  "
                  f"sauber {'ja' if result['sauber'] else 'NEIN'}  {seconds:.0f}s  {usage.get('cost_usd', 0):.3f} $", flush=True)
            if result["fakten_fehlend"]:
                print(f"         fehlt: {result['fakten_fehlend']}")
            if result["quellen_fehlend"]:
                print(f"         Quelle fehlt: {result['quellen_fehlend']}")
            if result["verboten_gefunden"]:
                print(f"         verboten: {result['verboten_gefunden']}")
            save()

    summary = summarize(rows)
    save()

    print("\nZusammenfassung")
    for key, value in summary.items():
        print(f"  {key:16} {value}")
    if args.baseline and args.baseline.exists():
        base = json.loads(args.baseline.read_text(encoding="utf-8"))["summary"]
        print(f"\nVergleich mit {args.baseline.name}")
        print(f"  {'modell':16} {base.get('modell', '?')} -> {summary['modell']}")
        for key in ("fakten_mittel", "quellen_ok", "sauber", "voll_bestanden", "dauer_mittel_s", "kosten_usd"):
            delta = summary[key] - base.get(key, 0)
            print(f"  {key:16} {base.get(key)} -> {summary[key]}  ({delta:+})")
    print(f"\nErgebnis: {out}")
    push_scores_to_langfuse(run_id, [r for r in rows if not r["answer"].startswith("[FEHLER]")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
