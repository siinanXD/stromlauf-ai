"""Ingest-Benchmark: Kennzeichen je Seite gegen Ground Truth, ohne Datenbank und ohne Modellaufruf.

Aufruf:  python eval/run_ingest.py --gold eval/ingest_gold/fb01.json [--doc PFAD --label scan] [--ocr]
                                   [--min 0.95] [--types device,terminal,plc_address] [--out eval/results]

--ocr legt vor der Messung eine unsichtbare Textebene auf die Seiten ohne Text (app/ingestion/ocr.py,
RapidOCR lokal) und misst diese Fassung; OCR-Seiten, -Sekunden und -Konfidenz stehen im Ergebnis.

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
import tempfile
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
Ocr = Callable[[Path, Path], tuple[Path, dict]]


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


def gate_failures(
    metrics: dict, minimum: float, types: Iterable[str], per_type: dict[str, float] | None = None
) -> list[str]:
    """Verfehlte Schwellen als lesbare Zeilen; ein gegateter Typ ohne Gold ist ein Fehler, kein Freifahrtschein.

    per_type ueberschreibt die gemeinsame Schwelle je Typ (Scan: Klemmen, Issue #66)."""
    failures = []
    for kind in types:
        threshold = (per_type or {}).get(kind, minimum)
        recall, precision = metrics[kind]["recall"], metrics[kind]["precision"]
        if recall is None:
            failures.append(f"{kind}: kein Gold fuer diesen Typ")
            continue
        for label, value in (("Recall", recall), ("Precision", precision)):
            if value is None or value < threshold:
                shown = "-" if value is None else f"{value:.2f}"
                failures.append(f"{kind}: {label} {shown} < {threshold:.2f}")
    return failures


def parse_minimums(values: Iterable[str]) -> dict[str, float]:
    """["terminal=0.75", ...] -> {"terminal": 0.75}; unbekannte Typen sind ein Fehler."""
    result = {}
    for value in values:
        kind, _, number = value.partition("=")
        kind = kind.strip()
        if kind not in TAG_TYPES:
            raise ValueError(
                f"unbekannter Typ in --min-for: {kind} (erlaubt: {', '.join(TAG_TYPES)})"
            )
        result[kind] = float(number)
    return result


def measure(doc: Path, doc_type: str) -> tuple[Pages, int | None, float]:
    """Dokument lesen wie beim Upload (ohne Vision) und die Kennzeichen je Seite liefern."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.pipeline import document_pieces, split_pieces, tag_rows

    start = time.perf_counter()
    read = document_pieces(doc, doc_type)
    rows = tag_rows(split_pieces(read.pieces))
    return by_page(rows), read.page_count, time.perf_counter() - start


def make_searchable(doc: Path, out_dir: Path) -> tuple[Path, dict]:
    """Durchsuchbare Fassung von doc in out_dir (OCR auf den Seiten ohne Textebene) und ihre Kennzahlen."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.ocr import searchable_pdf

    target = out_dir / f"{doc.stem}_ocr.pdf"
    return target, searchable_pdf(doc, target).summary()


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
    ]
    if ocr := summary.get("ocr"):
        lines += [
            f"OCR: {len(ocr['seiten'])} Seiten, {ocr['sekunden']:.1f} s, Konfidenz {_number(ocr['konfidenz'])} "
            "(unsichtbare Textebene, RapidOCR lokal auf der CPU).",
            "",
        ]
    lines += [
        f"Gate: Recall und Precision >= {gate['min']:.2f} fuer {', '.join(gate['typen']) or '-'}"
        + "".join(
            f", {kind} >= {value:.2f}" for kind, value in (gate.get("min_je_typ") or {}).items()
        )
        + f": {verdict}.",
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


def main(
    argv: list[str] | None = None, measure_fn: Measure = measure, ocr_fn: Ocr = make_searchable
) -> int:
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
    parser.add_argument(
        "--label",
        default="",
        help="Fassung im Dateinamen, z. B. scan, wenn --doc vom Gold abweicht",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Seiten ohne Textebene vorher per OCR durchsuchbar machen",
    )
    parser.add_argument(
        "--min-for",
        action="append",
        default=[],
        metavar="TYP=WERT",
        help="Schwelle fuer einen Typ statt --min, z. B. terminal=0.75 (mehrfach moeglich)",
    )
    args = parser.parse_args(argv)
    gated = [kind.strip() for kind in args.types.split(",") if kind.strip()]
    if unknown := sorted(set(gated) - set(TAG_TYPES)):
        parser.error(f"unbekannte Typen: {', '.join(unknown)} (erlaubt: {', '.join(TAG_TYPES)})")
    try:
        per_type = parse_minimums(args.min_for)
    except ValueError as exc:
        parser.error(str(exc))

    gold = load_gold(args.gold)
    doc = args.doc or ROOT / gold["dokument"]
    ocr_summary = None
    if args.ocr:
        with tempfile.TemporaryDirectory() as scratch:
            searchable, ocr_summary = ocr_fn(doc, Path(scratch))
            found, page_count, seconds = measure_fn(searchable, gold["doc_type"])
    else:
        found, page_count, seconds = measure_fn(doc, gold["doc_type"])
    metrics, deviations = compare(gold["seiten"], found)
    failures = gate_failures(metrics, args.min, gated, per_type) if args.min > 0 else []
    summary = {
        "gold": _relative(args.gold),
        "label": args.label,
        "dokument": _relative(doc),
        "doc_type": gold["doc_type"],
        "seiten": page_count,
        "sekunden": round(seconds, 2),
        "sekunden_je_seite": round(seconds / page_count, 2) if page_count else None,
        "ocr": ocr_summary,
        "metriken": metrics,
        "gate": {
            "min": args.min,
            "min_je_typ": per_type,
            "typen": gated if args.min > 0 else [],
            "ok": not failures,
            "verfehlt": failures,
        },
    }

    title = f"{args.gold.stem}_{args.label}" if args.label else args.gold.stem
    out = evallib.save_result(
        args.out / f"ingest_{title}_{evallib.run_id()}.json", summary, deviations
    )
    heading = f"{args.gold.stem} ({args.label})" if args.label else args.gold.stem
    markdown = render_markdown(heading, summary, deviations)
    out.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Ergebnis: {out}")
    if failures:
        print("Gate verfehlt: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
