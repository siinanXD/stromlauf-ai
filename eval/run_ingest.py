"""Ingest-Benchmark: Kennzeichen je Seite gegen Ground Truth, ohne Datenbank und ohne Modellaufruf.

Aufruf:  python eval/run_ingest.py --gold eval/ingest_gold/fb01.json [--doc PFAD] [--min 0.95]
                                   [--types device,terminal,plc_address] [--out eval/results]

Misst die Lesekette des Uploads (Docling + PDF-Rohtext -> Stuecke -> Kennzeichen) ueber dieselben
Funktionen wie die Pipeline: `document_pieces`, `split_pieces`, `tag_rows` aus
backend/app/ingestion/pipeline.py. Das Gold entsteht beim Zeichnen des Beispielplans
(scripts/example_docs/make_gold.py) und misst damit das Lesen, nicht die Kennzeichen-Grammatik;
die prueft backend/tests/test_tags.py.

Recall und Precision je Typ (device, terminal, plc_address, cross_ref) werden ueber alle Seiten
summiert (micro). Ergebnis: eval/results/ingest_<gold>_<zeitstempel>.json und .md.
Exit 1, wenn Recall oder Precision eines gegateten Typs unter --min liegen.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))

import evallib  # noqa: E402

TAG_TYPES = ("device", "terminal", "plc_address", "cross_ref")
GATED_DEFAULT = ("device", "terminal", "plc_address")
NO_PAGE = 0  # Funde ohne Seite (Nicht-PDF) landen hier statt verloren zu gehen

Pages = dict[int, dict[str, set[str]]]
Measure = Callable[[Path, str], tuple[Pages, int | None, float]]


def load_gold(path: Path) -> dict:
    """Gold-Datei lesen und pruefen; Seiten als int, Kennzeichen je Typ als Menge."""
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in ("dokument", "doc_type", "seiten") if key not in data]
    if missing:
        raise ValueError(f"{path.name}: Schluessel fehlen: {', '.join(missing)}")
    pages: Pages = {}
    for page, by_type in data["seiten"].items():
        unknown = sorted(set(by_type) - set(TAG_TYPES))
        if unknown:
            raise ValueError(
                f"{path.name}: unbekannte Typen auf Seite {page}: {', '.join(unknown)}"
            )
        pages[int(page)] = {kind: set(tags) for kind, tags in by_type.items()}
    return {**data, "seiten": pages}


def by_page(rows: Iterable) -> Pages:
    """Zeilen des Kennzeichen-Index (tag, tag_type, page) je Seite und Typ gruppieren."""
    pages: Pages = {}
    for row in rows:
        page = NO_PAGE if row.page is None else row.page
        pages.setdefault(page, {}).setdefault(str(row.tag_type), set()).add(row.tag)
    return pages


def _ratio(hits: int, total: int) -> float | None:
    """Exakter Anteil; gerundet wird nur in der Anzeige."""
    return None if total == 0 else hits / total


def compare(gold: Pages, found: Pages, types: Iterable[str] = TAG_TYPES) -> tuple[dict, list[dict]]:
    """Micro-Recall und -Precision je Typ ueber alle Seiten, dazu fehlende/fremde Kennzeichen je Seite."""
    types = list(types)
    totals = {kind: {"tp": 0, "fp": 0, "fn": 0} for kind in types}
    deviations = []
    for page in sorted(set(gold) | set(found)):
        entry: dict = {"seite": page, "fehlend": {}, "fremd": {}}
        for kind in types:
            want = gold.get(page, {}).get(kind, set())
            got = found.get(page, {}).get(kind, set())
            totals[kind]["tp"] += len(want & got)
            totals[kind]["fn"] += len(want - got)
            totals[kind]["fp"] += len(got - want)
            if want - got:
                entry["fehlend"][kind] = sorted(want - got)
            if got - want:
                entry["fremd"][kind] = sorted(got - want)
        if entry["fehlend"] or entry["fremd"]:
            deviations.append(entry)
    metrics = {
        kind: {
            **counts,
            "recall": _ratio(counts["tp"], counts["tp"] + counts["fn"]),
            "precision": _ratio(counts["tp"], counts["tp"] + counts["fp"]),
        }
        for kind, counts in totals.items()
    }
    return metrics, deviations


def gate_failures(metrics: dict, minimum: float, types: Iterable[str]) -> list[str]:
    """Verfehlte Schwellen als lesbare Zeilen; ein gegateter Typ ohne Gold ist ein Fehler, kein Freifahrtschein."""
    failures = []
    for kind in types:
        recall, precision = metrics[kind]["recall"], metrics[kind]["precision"]
        if recall is None:
            failures.append(f"{kind}: kein Gold fuer diesen Typ")
            continue
        for label, value in (("Recall", recall), ("Precision", precision)):
            if value is None or value < minimum:
                shown = "-" if value is None else f"{value:.2f}"
                failures.append(f"{kind}: {label} {shown} < {minimum:.2f}")
    return failures


def measure(doc: Path, doc_type: str) -> tuple[Pages, int | None, float]:
    """Dokument lesen wie beim Upload (ohne Vision) und die Kennzeichen je Seite liefern."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.pipeline import document_pieces, split_pieces, tag_rows

    start = time.perf_counter()
    read = document_pieces(doc, doc_type)
    rows = tag_rows(split_pieces(read.pieces))
    return by_page(rows), read.page_count, time.perf_counter() - start


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def render_markdown(title: str, summary: dict, deviations: list[dict]) -> str:
    gate = summary["gate"]
    verdict = "bestanden" if gate["ok"] else "verfehlt: " + "; ".join(gate["verfehlt"])
    lines = [
        f"# Ingest-Benchmark {title}",
        "",
        f"Dokument `{summary['dokument']}`, {summary['seiten'] or '-'} Seiten, {summary['sekunden']:.1f} s "
        f"({_number(summary['sekunden_je_seite'])} s je Seite). Gold `{summary['gold']}`.",
        "",
        f"Gate: Recall und Precision >= {gate['min']:.2f} fuer {', '.join(gate['typen']) or '-'}: {verdict}.",
        "",
        "| Typ | Gold | gefunden | Treffer | Recall | Precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for kind, m in summary["metriken"].items():
        lines.append(
            f"| {kind} | {m['tp'] + m['fn']} | {m['tp'] + m['fp']} | {m['tp']} | "
            f"{_number(m['recall'])} | {_number(m['precision'])} |"
        )
    lines += ["", "## Abweichungen je Seite", ""]
    if not deviations:
        lines.append("keine")
    for entry in deviations:
        parts = [f"fehlt {kind}: {', '.join(tags)}" for kind, tags in entry["fehlend"].items()]
        parts += [f"fremd {kind}: {', '.join(tags)}" for kind, tags in entry["fremd"].items()]
        lines.append(f"- Seite {entry['seite']}: " + "; ".join(parts))
    return "\n".join(lines) + "\n"


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None, measure_fn: Measure = measure) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--gold", type=Path, required=True, help="Gold-Datei, z. B. eval/ingest_gold/fb01.json"
    )
    parser.add_argument(
        "--doc", type=Path, help="Zu lesendes Dokument; Standard: 'dokument' aus dem Gold"
    )
    parser.add_argument(
        "--min", type=float, default=0.0, help="Exit 1, wenn Recall oder Precision darunter"
    )
    parser.add_argument(
        "--types", default=",".join(GATED_DEFAULT), help="Gegatete Typen, kommagetrennt"
    )
    parser.add_argument("--out", type=Path, default=RESULTS, help="Ordner fuer JSON und Markdown")
    args = parser.parse_args(argv)
    gated = [kind.strip() for kind in args.types.split(",") if kind.strip()]
    if unknown := sorted(set(gated) - set(TAG_TYPES)):
        parser.error(f"unbekannte Typen: {', '.join(unknown)} (erlaubt: {', '.join(TAG_TYPES)})")

    gold = load_gold(args.gold)
    doc = args.doc or ROOT / gold["dokument"]
    found, page_count, seconds = measure_fn(doc, gold["doc_type"])
    metrics, deviations = compare(gold["seiten"], found)
    failures = gate_failures(metrics, args.min, gated) if args.min > 0 else []
    summary = {
        "gold": _relative(args.gold),
        "dokument": _relative(doc),
        "doc_type": gold["doc_type"],
        "seiten": page_count,
        "sekunden": round(seconds, 2),
        "sekunden_je_seite": round(seconds / page_count, 2) if page_count else None,
        "metriken": metrics,
        "gate": {
            "min": args.min,
            "typen": gated if args.min > 0 else [],
            "ok": not failures,
            "verfehlt": failures,
        },
    }

    name = f"ingest_{args.gold.stem}_{evallib.run_id()}"
    out = evallib.save_result(args.out / f"{name}.json", summary, deviations)
    markdown = render_markdown(args.gold.stem, summary, deviations)
    out.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Ergebnis: {out}")
    if failures:
        print("Gate verfehlt: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
