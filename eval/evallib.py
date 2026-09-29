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
COMPARE_KEYS = ("fakten_mittel", "quellen_ok", "zitate_gueltig", "zitate_geprueft", "sauber", "werkzeug_ok", "voll_bestanden", "dauer_mittel_s")


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


def parse_sse(lines: Iterable[str]) -> tuple[str, list[dict], list[str], dict]:
    """SSE-Strom von /api/chat: (Antwort, Quellen, Werkzeugaufrufe, Lauf-Infos).

    Die Lauf-Infos enthalten die Konversations-ID (in Langfuse die Session dieses Chats), den
    summierten Verbrauch aus den usage-Ereignissen, eines je Modellaufruf, und unter ``answer_meta``
    das meta-Event (referenzierte Bauteile, geprueft Belege). Ein error-Event wird an die Antwort angehaengt.
    """
    answer: list[str] = []
    sources: list[dict] = []
    tools: list[str] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "model": ""}
    meta = {"conversation_id": "", "usage": usage}
    event = None
    for line in lines:
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event:
            data = json.loads(line[5:].strip() or "null")
            if event == "token":
                answer.append(data["text"])
            elif event == "conversation":
                meta["conversation_id"] = data.get("id", "")
            elif event == "sources":
                sources = data
            elif event == "tool_start":
                tools.append(data["name"])
            elif event == "usage":
                usage["input_tokens"] += data.get("input_tokens", 0)
                usage["output_tokens"] += data.get("output_tokens", 0)
                usage["calls"] += 1
                usage["model"] = data.get("model") or usage["model"]
            elif event == "meta":
                meta["answer_meta"] = data
            elif event == "error":
                answer.append(f"\n{ERROR_PREFIX} {data.get('message')}")
            elif event == "done":
                break
    return "".join(answer), sources, tools, meta


# --- Bewertung ----------------------------------------------------------------------------------


def score(question: dict, answer: str, sources: list[dict], tools: list[str] | None = None,
          check_sources: bool = True, meta: dict | None = None) -> dict:
    """Regeln statt Richter: Regex-Muster (Gross/Klein egal), zitierte Dateien, verbotene Muster, Werkzeuge.

    ``meta`` ist das meta-Event der Antwort: seine ``citation_checks`` (Zitat-Resolver im Backend, Issue #46)
    ergeben ``zitate_gueltig`` (Anteil gueltiger Belege) und ``zitate_geprueft`` (Anteil pruefbarer Orte);
    ohne Belege oder ohne meta bleiben beide None.
    """
    hits = [bool(re.search(p, answer, re.IGNORECASE)) for p in question["must_contain"]]
    forbidden = [p for p in question.get("must_not_contain", []) if re.search(p, answer, re.IGNORECASE)]
    cited = {s.get("filename", "") for s in sources}
    missing_sources = [f for f in question.get("expect_sources", []) if f not in cited] if check_sources else []
    expected_tools = question.get("tools") or []
    werkzeug_ok = None if tools is None or not expected_tools else all(t in tools for t in expected_tools)
    checks = (meta or {}).get("citation_checks") or []
    unchecked = [c.get("text", "") for c in checks if not c.get("checked")]
    invalid = [c.get("text", "") for c in checks if not c.get("valid")]
    checked_n = len(checks) - len(unchecked)
    return {
        "fakten": sum(hits) / len(hits) if hits else 1.0,
        "fakten_fehlend": [p for p, h in zip(question["must_contain"], hits, strict=True) if not h],
        "quellen_ok": not missing_sources,
        "quellen_fehlend": missing_sources,
        "sauber": not forbidden,
        "verboten_gefunden": forbidden,
        "werkzeug_ok": werkzeug_ok,
        "zitate_belege": len(checks),
        "zitate_gueltig": (checked_n - len(invalid)) / checked_n if checked_n else None,
        "zitate_geprueft": checked_n / len(checks) if checks else None,
        "zitate_ungueltig": invalid,
        "zitate_ungeprueft": unchecked,
    }


def below_threshold(summary: dict, minimum: float | None, key: str = "zitate_gueltig") -> bool:
    """Gate: True, wenn die Kennzahl fehlt oder unter der Schwelle liegt; ohne Schwelle nie."""
    if minimum is None:
        return False
    value = summary.get(key)
    return value is None or value < minimum


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
    # Belege werden ueber alle bewerteten Antworten zusammengezaehlt (contract.md: "valid citations >= 95 %"),
    # nicht je Antwort gemittelt; gueltig zaehlt nur unter den pruefbaren Belegen
    total = sum(r["score"].get("zitate_belege") or 0 for r in scored)
    unchecked = sum(len(r["score"].get("zitate_ungeprueft") or []) for r in scored)
    invalid = sum(len(r["score"].get("zitate_ungueltig") or []) for r in scored)
    checked = total - unchecked

    return {
        "fragen": len(rows),
        "bewertet": len(scored),
        "nicht_bewertet_fehler": len(failed),
        "fakten_mittel": round(sum(r["score"]["fakten"] for r in scored) / n, 3),
        "quellen_ok": round(sum(r["score"]["quellen_ok"] for r in scored) / n, 3),
        "zitate_belege": total,
        "zitate_antworten": sum(1 for r in scored if r["score"].get("zitate_belege")),
        "zitate_gueltig": round((checked - invalid) / checked, 3) if checked else None,
        "zitate_geprueft": round(checked / total, 3) if total else None,
        "sauber": round(sum(r["score"]["sauber"] for r in scored) / n, 3),
        "werkzeug_ok": round(sum(r["score"]["werkzeug_ok"] for r in with_tools) / len(with_tools), 3) if with_tools else None,
        "voll_bestanden": sum(passed(r["score"]) for r in scored),
        "dauer_mittel_s": round(sum(r.get("dauer_s", 0.0) for r in scored) / n, 1),
        **usage_total(rows),
    }


def usage_total(rows: list[dict]) -> dict:
    """Tokens, Modellaufrufe und Kosten eines Laufs. Leer, wenn keine Zeile Verbrauch mitbringt."""
    used = [r["usage"] for r in rows if r.get("usage")]
    if not used:
        return {}
    return {
        "tokens_ein": sum(u.get("input_tokens", 0) for u in used),
        "tokens_aus": sum(u.get("output_tokens", 0) for u in used),
        "modellaufrufe": sum(u.get("calls", 0) for u in used),
        "kosten_usd": round(sum(u.get("cost_usd", 0.0) for u in used), 4),
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


def run_id() -> str:
    return f"{datetime.now():%Y-%m-%d_%H-%M-%S}"


def save_result(out: Path, summary: dict, rows: list[dict]) -> Path:
    """Schreibt (bzw. ueberschreibt) eine Ergebnisdatei; nach jeder Frage aufrufbar."""
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_result(results_dir: Path, prefix: str, summary: dict, rows: list[dict]) -> Path:
    return save_result(results_dir / f"{prefix}{run_id()}.json", summary, rows)


def print_row(index: int, total: int, question: dict, result: dict, seconds: float | None = None) -> None:
    flag = "OK " if passed(result) else "-- "
    tools = "" if result.get("werkzeug_ok") is None else f"  werkzeug {'ja' if result['werkzeug_ok'] else 'NEIN'}"
    cites = "" if result.get("zitate_gueltig") is None else f"  zitate {result['zitate_gueltig']:.2f}"
    time_text = f"  {seconds:.0f}s" if seconds is not None else ""
    print(f"[{index}/{total}] {question['id']}: {question['question'][:70]}", flush=True)
    print(f"      {flag} fakten {result['fakten']:.2f}  quellen {'ja' if result['quellen_ok'] else 'NEIN'}  "
          f"sauber {'ja' if result['sauber'] else 'NEIN'}{tools}{cites}{time_text}", flush=True)
    if result["fakten_fehlend"]:
        print(f"         fehlt: {result['fakten_fehlend']}")
    if result["quellen_fehlend"]:
        print(f"         Quelle fehlt: {result['quellen_fehlend']}")
    if result["verboten_gefunden"]:
        print(f"         verboten: {result['verboten_gefunden']}")
    if result.get("zitate_ungueltig"):
        print(f"         Beleg ungueltig: {result['zitate_ungueltig']}")


def print_summary(summary: dict, baseline_path: Path | None = None) -> None:
    print("\nZusammenfassung")
    for key, value in summary.items():
        print(f"  {key:22} {value}")
    if baseline_path and baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))["summary"]
        print(f"\nVergleich mit {baseline_path.name}")
        for key, old, new, delta in compare(summary, base):
            print(f"  {key:22} {old} -> {new}  ({delta:+.3f})")
