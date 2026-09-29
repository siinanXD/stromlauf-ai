"""Zwei Agentenlaeufe nebeneinander: Qualitaet, Kosten, Dauer je Modell (Provider-Vergleich, ohne Modellaufruf).

Aufruf:  python eval/compare_runs.py eval/results/<lauf_a>.json eval/results/<lauf_b>.json [--out eval/results/vergleich.md]

Liest zwei Ergebnisdateien von run_eval.py (summary + results, gleiche Fragen) und schreibt Markdown: Kennzahlen
(fakten_mittel, quellen_ok, sauber, werkzeug_ok, voll_bestanden, Tokens, Kosten, Kosten je Antwort, Dauer) und je
Frage Fakten, Quellen, sauber, Kosten und Dauer beider Laeufe; Fragen mit unterschiedlicher Bewertung sind markiert.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

METRICS = (
    "fragen",
    "bewertet",
    "nicht_bewertet_fehler",
    "fakten_mittel",
    "quellen_ok",
    "zitate_gueltig",
    "zitate_geprueft",
    "zitate_belege",
    "teile_praezision",
    "teile_recall",
    "sauber",
    "werkzeug_ok",
    "voll_bestanden",
    "tokens_ein",
    "tokens_aus",
    "modellaufrufe",
    "kosten_usd",
    "kosten_je_antwort_usd",
    "dauer_mittel_s",
    "p95_s",
    "fehlerrate",
)


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def model_of(run: dict) -> str:
    """Haeufigster Modellname aus den Antworten (die API liefert datierte IDs); "unbekannt" ohne Verbrauchsdaten."""
    models = Counter(r.get("usage", {}).get("model") for r in run.get("results", []) if r.get("usage", {}).get("model"))
    return models.most_common(1)[0][0] if models else "unbekannt"


def _summary(run: dict) -> dict:
    summary = dict(run.get("summary", {}))
    answered = summary.get("bewertet") or len(run.get("results", [])) or 1
    if "kosten_usd" in summary:
        summary["kosten_je_antwort_usd"] = round(summary["kosten_usd"] / answered, 4)
    return summary


def _score(row: dict | None, key: str):
    return None if row is None else row.get("score", {}).get(key)


def _cost(row: dict | None) -> float | None:
    if row is None or not row.get("usage"):
        return None
    return row["usage"].get("cost_usd")


def compare(a: dict, b: dict) -> dict:
    """Kennzahlen und Fragen beider Laeufe; Fragen kommen aus Lauf a, Lauf b wird ueber die Fragen-ID zugeordnet."""
    sa, sb = _summary(a), _summary(b)
    kennzahlen = [{"kennzahl": key, "a": sa.get(key), "b": sb.get(key)} for key in METRICS if key in sa or key in sb]
    rows_b = {row["id"]: row for row in b.get("results", [])}
    fragen = []
    for ra in a.get("results", []):
        rb = rows_b.get(ra["id"])
        entry = {
            "id": ra["id"],
            "frage": ra.get("question", ""),
            "fakten": (_score(ra, "fakten"), _score(rb, "fakten")),
            "quellen_ok": (_score(ra, "quellen_ok"), _score(rb, "quellen_ok")),
            "zitate_gueltig": (_score(ra, "zitate_gueltig"), _score(rb, "zitate_gueltig")),
            "sauber": (_score(ra, "sauber"), _score(rb, "sauber")),
            "kosten_usd": (_cost(ra), _cost(rb)),
            "dauer_s": (ra.get("dauer_s"), None if rb is None else rb.get("dauer_s")),
        }
        entry["unterschied"] = rb is None or any(
            entry[key][0] != entry[key][1] for key in ("fakten", "quellen_ok", "zitate_gueltig", "sauber")
        )
        fragen.append(entry)
    return {"modelle": (model_of(a), model_of(b)), "kennzahlen": kennzahlen, "fragen": fragen}


def _fmt(value, money: bool = False) -> str:
    if value is None:
        return "–"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, float):
        return f"{value:.4f}" if money else f"{value:g}"
    return str(value)


def render_markdown(comparison: dict) -> str:
    a, b = comparison["modelle"]
    lines = [f"# Vergleich {a} gegen {b}", "", f"| Kennzahl | {a} | {b} |", "| --- | --- | --- |"]
    for row in comparison["kennzahlen"]:
        money = row["kennzahl"].startswith("kosten")
        lines.append(f"| {row['kennzahl']} | {_fmt(row['a'], money)} | {_fmt(row['b'], money)} |")
    lines += ["", "## Fragen", "",
              "| Frage | Fakten A / B | Quellen A / B | Zitate A / B | sauber A / B | Kosten A / B (USD) | Dauer A / B (s) | |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in comparison["fragen"]:
        mark = "≠" if row["unterschied"] else ""
        lines.append(
            f"| `{row['id']}` {row['frage']} | {_pair(row, 'fakten')} | {_pair(row, 'quellen_ok')} | {_pair(row, 'zitate_gueltig')} | "
            f"{_pair(row, 'sauber')} | {_pair(row, 'kosten_usd', True)} | {_pair(row, 'dauer_s')} | {mark} |"
        )
    return "\n".join(lines) + "\n"


def _pair(row: dict, key: str, money: bool = False) -> str:
    return f"{_fmt(row[key][0], money)} / {_fmt(row[key][1], money)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_a", type=Path, help="Ergebnisdatei Lauf A (run_eval.py)")
    parser.add_argument("run_b", type=Path, help="Ergebnisdatei Lauf B")
    parser.add_argument("--out", type=Path, help="Markdown-Datei; ohne --out auf die Konsole")
    args = parser.parse_args(argv)
    text = render_markdown(compare(load(args.run_a), load(args.run_b)))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"geschrieben: {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
