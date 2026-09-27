"""Gemeinsame Logik des Eval-Harness: Fragen laden und pruefen, SSE lesen, bewerten, zusammenfassen.

Ohne Netz und ohne Modell; die Skripte run_eval.py, run_retrieval.py und rescore.py sind duenne Huellen.
"""

import json
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

RETRIEVAL_MODES = ("tag", "semantic", "keyword", "fact", "signal", "calc", "site")
NO_FILES = {"signal", "calc", "site"}  # Retrieval-Modi ohne zitierte Dateinamen: quellen gilt als erfuellt
ERROR_PREFIX = "[FEHLER]"
COMPARE_KEYS = ("fakten_mittel", "quellen_ok", "sauber", "werkzeug_ok", "voll_bestanden", "dauer_mittel_s")


# --- Fragen -----------------------------------------------------------------------------------


def load_questions(path: Path, only: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    problems = validate_questions(rows)
    if problems:
        raise ValueError("questions.jsonl fehlerhaft:\n  " + "\n  ".join(problems))
    if only:
        needle = only.lower()
        rows = [r for r in rows if needle in r["id"].lower() or needle in (r.get("source") or "").lower()]
    return rows


def validate_questions(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        qid = row.get("id", "?")
        if qid in seen:
            problems.append(f"{qid}: ID doppelt")
        seen.add(qid)
        if not str(row.get("question", "")).strip():
            problems.append(f"{qid}: Frage fehlt")
        if row.get("agent", True) and not row.get("source"):
            problems.append(f"{qid}: Wissensquelle fehlt")
        for key in ("must_contain", "must_not_contain"):
            for pattern in row.get(key, []):
                try:
                    re.compile(pattern)
                except re.error as err:
                    problems.append(f"{qid}: Muster {pattern!r} ungültig: {err}")
        retrieval = row.get("retrieval")
        if retrieval is not None:
            if retrieval.get("mode") not in RETRIEVAL_MODES:
                problems.append(f"{qid}: retrieval.mode {retrieval.get('mode')!r} unbekannt")
            if "query" not in retrieval:
                problems.append(f"{qid}: retrieval.query fehlt")
        if row.get("agent") is False and retrieval is None:
            problems.append(f"{qid}: agent=false braucht retrieval")
    return problems


# --- Agentenantwort lesen -----------------------------------------------------------------------


def parse_sse(lines: Iterable[str]) -> tuple[str, list[dict], list[str]]:
    """SSE-Strom von /api/chat: (Antwort, Quellen, Werkzeugaufrufe). Ein error-Event wird an die Antwort angehaengt."""
    answer: list[str] = []
    sources: list[dict] = []
    tools: list[str] = []
    event = None
    for line in lines:
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
            elif event == "error":
                answer.append(f"\n{ERROR_PREFIX} {data.get('message')}")
            elif event == "done":
                break
    return "".join(answer), sources, tools


# --- Bewertung ----------------------------------------------------------------------------------


def score(question: dict, answer: str, sources: list[dict], tools: list[str] | None = None,
          check_sources: bool = True) -> dict:
    """Regeln statt Richter: Regex-Muster (Gross/Klein egal), zitierte Dateien, verbotene Muster, Werkzeuge."""
    hits = [bool(re.search(p, answer, re.IGNORECASE)) for p in question["must_contain"]]
    forbidden = [p for p in question.get("must_not_contain", []) if re.search(p, answer, re.IGNORECASE)]
    cited = {s.get("filename", "") for s in sources}
    missing_sources = [f for f in question.get("expect_sources", []) if f not in cited] if check_sources else []
    expected_tools = question.get("tools") or []
    werkzeug_ok = None if tools is None or not expected_tools else all(t in tools for t in expected_tools)
    return {
        "fakten": sum(hits) / len(hits) if hits else 1.0,
        "fakten_fehlend": [p for p, h in zip(question["must_contain"], hits, strict=True) if not h],
        "quellen_ok": not missing_sources,
        "quellen_fehlend": missing_sources,
        "sauber": not forbidden,
        "verboten_gefunden": forbidden,
        "werkzeug_ok": werkzeug_ok,
    }


def passed(result: dict) -> bool:
    return (result["fakten"] == 1.0 and result["quellen_ok"] and result["sauber"]
            and result.get("werkzeug_ok") is not False)


def is_error(row: dict) -> bool:
    """Netz-/API-Fehler: vom Skript vorangestellt oder vom Backend als error-Event in den Strom geschrieben."""
    return ERROR_PREFIX in str(row.get("answer", ""))


def summarize(rows: list[dict]) -> dict:
    """API-/Netzfehler zaehlen nicht als falsche Antwort, sie werden getrennt ausgewiesen."""
    failed = [r for r in rows if is_error(r)]
    scored = [r for r in rows if not is_error(r)]
    n = len(scored) or 1
    with_tools = [r for r in scored if isinstance(r["score"].get("werkzeug_ok"), bool)]
    return {
        "fragen": len(rows),
        "bewertet": len(scored),
        "nicht_bewertet_fehler": len(failed),
        "fakten_mittel": round(sum(r["score"]["fakten"] for r in scored) / n, 3),
        "quellen_ok": round(sum(r["score"]["quellen_ok"] for r in scored) / n, 3),
        "sauber": round(sum(r["score"]["sauber"] for r in scored) / n, 3),
        "werkzeug_ok": round(sum(r["score"]["werkzeug_ok"] for r in with_tools) / len(with_tools), 3) if with_tools else None,
        "voll_bestanden": sum(passed(r["score"]) for r in scored),
        "dauer_mittel_s": round(sum(r.get("dauer_s", 0.0) for r in scored) / n, 1),
    }


def compare(summary: dict, baseline: dict) -> list[tuple[str, object, object, float]]:
    rows = []
    for key in COMPARE_KEYS:
        if key in summary and key in baseline and summary[key] is not None and baseline[key] is not None:
            rows.append((key, baseline[key], summary[key], summary[key] - baseline[key]))
    return rows


# --- Retrieval-Antworten abflachen ------------------------------------------------------------------


def _unique(names: Iterable[str | None]) -> list[str]:
    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return seen


def flatten(mode: str, payload: object) -> tuple[str, list[str]]:
    """Endpunkt-Antwort als Text plus zitierte Dateinamen, damit dieselben Regeln wie fuer den Agenten gelten."""
    if payload is None:
        return "", []
    if mode in {"tag", "semantic", "keyword"}:
        return payload["text"], _unique(r.get("filename") for r in payload.get("refs", []))
    if mode == "fact":
        lines = [payload.get("title") or "", payload.get("bom_line") or ""]
        lines += [f"{row['label']}: " + ", ".join(v["text"] for v in row["values"]) for row in payload.get("rows", [])]
        files = _unique(v.get("filename") for row in payload.get("rows", []) for v in row["values"])
        return "\n".join(line for line in lines if line), files
    if mode == "signal":
        lines = []
        for node in payload.get("nodes", []):
            lines.append(f"{node['id']} | {node.get('label', '')} | {node.get('ref', '')}")
            if node.get("detail"):
                lines.append(node["detail"])
        return "\n".join(lines), []
    return json.dumps(payload, ensure_ascii=False), []


# --- Ausgabe ------------------------------------------------------------------------------------


def write_result(results_dir: Path, prefix: str, summary: dict, rows: list[dict]) -> Path:
    results_dir.mkdir(exist_ok=True)
    out = results_dir / f"{prefix}{datetime.now():%Y-%m-%d_%H-%M-%S}.json"
    out.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def print_row(index: int, total: int, question: dict, result: dict, seconds: float | None = None) -> None:
    flag = "OK " if passed(result) else "-- "
    tools = "" if result.get("werkzeug_ok") is None else f"  werkzeug {'ja' if result['werkzeug_ok'] else 'NEIN'}"
    time_text = f"  {seconds:.0f}s" if seconds is not None else ""
    print(f"[{index}/{total}] {question['id']}: {question['question'][:70]}", flush=True)
    print(f"      {flag} fakten {result['fakten']:.2f}  quellen {'ja' if result['quellen_ok'] else 'NEIN'}  "
          f"sauber {'ja' if result['sauber'] else 'NEIN'}{tools}{time_text}", flush=True)
    if result["fakten_fehlend"]:
        print(f"         fehlt: {result['fakten_fehlend']}")
    if result["quellen_fehlend"]:
        print(f"         Quelle fehlt: {result['quellen_fehlend']}")
    if result["verboten_gefunden"]:
        print(f"         verboten: {result['verboten_gefunden']}")


def print_summary(summary: dict, baseline_path: Path | None = None) -> None:
    print("\nZusammenfassung")
    for key, value in summary.items():
        print(f"  {key:22} {value}")
    if baseline_path and baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))["summary"]
        print(f"\nVergleich mit {baseline_path.name}")
        for key, old, new, delta in compare(summary, base):
            print(f"  {key:22} {old} -> {new}  ({delta:+.3f})")
