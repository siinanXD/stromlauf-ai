"""Planleser-Benchmark: Kanten aus dem Stromlaufplan gegen Ground Truth und gegen die Tabellen, ohne DB und Modell.

Aufruf:  python eval/run_plan_graph.py --gold eval/ingest_gold/fb01.json [--doc PFAD] [--min-precision 0.95]
                                       [--out eval/results]

Ebene 1, Leitungen: die Kanten mit Herkunft "leitung" aus `plan_wires.compute_edges` (ohne Cache) gegen "wires" im
Gold, das scripts/example_docs/make_gold.py beim Zeichnen mitschreibt. Verglichen werden je Seite ungerichtete Paare,
Precision und Recall ueber alle Seiten (micro). Kanten aus der Lage im Plan sind keine gezeichneten Leitungen; sie
zaehlen nur auf Ebene 2.

Ebene 2, Tabellen: der Graph aus dem Plan gegen den Graphen aus Klemmenplan, Stueckliste, Symboltabelle und AWL im
Ordner des Plans (`app.api.signal._graph`). Anschluesse gehen in ihrem Geraet auf ("-K1:A1" -> "-K1"). Gezaehlt
werden Plan-Kanten mit einer Klemme oder SPS-Adresse an einem Ende, deren beide Enden die Tabellen kennen: Nur dort
legen die Tabellen die Verbindungen fest. Verdrahtung zwischen Geraeten und Versorgung stehen nicht im Klemmenplan.

--min-precision: Exit 1, wenn eine Precision darunter liegt oder der Leser keine Kante findet. Recall wird nur
berichtet. Ergebnis: eval/results/plan_graph_<gold>_<zeitstempel>.json und .md.
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))

import evallib  # noqa: E402

Pair = frozenset[str]
Pages = dict[int, set[Pair]]
TABLE_TYPES = ("terminal_plan", "bom", "plc_symbols", "plc_program")
_ADDRESS = re.compile(r"[EA]\d+\.[0-7]")


def _backend() -> None:
    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


def load_wires(path: Path) -> tuple[str, Pages]:
    """Dokument und verbundene Anschluesse je Seite aus dem Gold."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "wires" not in data:
        raise ValueError(f"{path.name}: keine Leitungen (wires); make_gold.py --write")
    pages = {
        int(page): {frozenset(pair) for pair in pairs} for page, pairs in data["wires"].items()
    }
    return data["dokument"], pages


def by_page(edges: Iterable) -> Pages:
    """Plan-Kanten (source, target, page) als ungerichtete Paare je Seite."""
    pages: Pages = {}
    for edge in edges:
        if edge.source != edge.target:
            pages.setdefault(edge.page, set()).add(frozenset((edge.source, edge.target)))
    return pages


def _ratio(hits: int, total: int) -> float | None:
    return None if total == 0 else hits / total


def compare_wires(gold: Pages, found: Pages) -> tuple[dict, list[dict]]:
    """Micro-Precision und -Recall ueber alle Seiten, dazu fehlende und fremde Paare je Seite."""
    tp = fp = fn = 0
    deviations = []
    for page in sorted(set(gold) | set(found)):
        want, got = gold.get(page, set()), found.get(page, set())
        tp, fp, fn = tp + len(want & got), fp + len(got - want), fn + len(want - got)
        if want != got:
            deviations.append(
                {
                    "seite": page,
                    "fehlend": sorted(sorted(pair) for pair in want - got),
                    "fremd": sorted(sorted(pair) for pair in got - want),
                }
            )
    metrics = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
    }
    return metrics, deviations


def collapse(node: str) -> str:
    """Anschluss -> Geraet ("-K1:A1" -> "-K1"); Klemmen und Adressen bleiben."""
    if node.startswith("-") and ":" in node and not node.startswith("-X"):
        return node.split(":", 1)[0]
    return node


def _measured(node: str) -> bool:
    """Klemme mit Nummer oder E/A-Adresse: Dafuer legen die Tabellen alle Verbindungen fest."""
    return (node.startswith("-X") and ":" in node) or bool(_ADDRESS.fullmatch(node))


def table_pairs(graph) -> tuple[set[str], set[Pair]]:
    """Knoten und ungerichtete Kanten des Tabellengraphen ohne Programmteile, Anschluesse im Geraet."""
    nodes = {
        collapse(node.id)
        for node in graph.nodes.values()
        if node.kind not in ("network", "variable")
    }
    pairs = set()
    for source, target in graph.edges:
        kinds = {graph.nodes[source].kind, graph.nodes[target].kind}
        a, b = collapse(source), collapse(target)
        if a != b and not kinds & {"network", "variable"}:
            pairs.add(frozenset((a, b)))
    return nodes, pairs


def compare_tables(found: Pages, nodes: set[str], pairs: set[Pair]) -> tuple[dict, list[list[str]]]:
    """Precision der Plan-Kanten gegen die Tabellen; Recall gegen die Tabellenkanten an Klemmen und Adressen."""
    plan = {
        frozenset(collapse(node) for node in pair)
        for page in found.values()
        for pair in page
        if len({collapse(node) for node in pair}) == 2
    }
    scoped = {pair for pair in plan if pair <= nodes and any(_measured(node) for node in pair)}
    wanted = {pair for pair in pairs if any(_measured(node) for node in pair)}
    hits = scoped & pairs
    metrics = {
        "gezaehlt": len(scoped),
        "nicht_gezaehlt": len(plan - scoped),
        "bestaetigt": len(hits),
        "precision": _ratio(len(hits), len(scoped)),
        "tabellenkanten": len(wanted),
        "recall": _ratio(len(hits), len(wanted)),
    }
    return metrics, sorted(sorted(pair) for pair in scoped - pairs)


def measure(doc: Path) -> tuple[list, float]:
    """Kanten des Leitungslesers, ohne Cache."""
    _backend()
    from app.ingestion.plan_wires import compute_edges

    start = time.perf_counter()
    edges = compute_edges(doc)
    return edges, time.perf_counter() - start


def table_graph(doc: Path):
    """Graph aus den Tabellen im Ordner des Plans; der Dokumenttyp kommt aus der Erkennung beim Upload."""
    _backend()
    from app.api.signal import _graph
    from app.ingestion.doctype import detect

    files = []
    for path in sorted(doc.parent.iterdir()):
        if path == doc or not path.is_file():
            continue
        doc_type = str(detect(path.name, path).doc_type)
        if doc_type in TABLE_TYPES:
            files.append((doc_type, str(path), path.stat().st_mtime))
    return _graph(tuple(files)) if files else None


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def gate_failures(wires: dict, tables: dict | None, minimum: float) -> list[str]:
    failures = []
    if wires["precision"] is None:
        failures.append("Leitungen: keine Kante gefunden")
    elif wires["precision"] < minimum:
        failures.append(f"Leitungen: Precision {wires['precision']:.2f} < {minimum:.2f}")
    if tables and tables["precision"] is not None and tables["precision"] < minimum:
        failures.append(f"Tabellen: Precision {tables['precision']:.2f} < {minimum:.2f}")
    return failures


def render_markdown(title: str, summary: dict, deviations: list[dict], foreign: list) -> str:
    gate = summary["gate"]
    wires, tables = summary["leitungen"], summary["tabellen"]
    verdict = "bestanden" if gate["ok"] else "verfehlt: " + "; ".join(gate["verfehlt"])
    lines = [
        f"# Planleser-Benchmark {title}",
        "",
        f"Dokument `{summary['dokument']}`, {summary['kanten']} Kanten in {summary['sekunden']:.2f} s "
        f"({', '.join(f'{via} {count}' for via, count in summary['herkunft'].items()) or '-'}). "
        f"Gold `{summary['gold']}`.",
        "",
        f"Gate: Precision >= {gate['min']:.2f} auf beiden Ebenen: {verdict}.",
        "",
        "| Ebene | Gold/Tabelle | gefunden | Treffer | Precision | Recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| Leitungen | {wires['tp'] + wires['fn']} | {wires['tp'] + wires['fp']} | {wires['tp']} | "
        f"{_number(wires['precision'])} | {_number(wires['recall'])} |",
    ]
    if tables:
        lines.append(
            f"| Tabellen | {tables['tabellenkanten']} | {tables['gezaehlt']} | {tables['bestaetigt']} | "
            f"{_number(tables['precision'])} | {_number(tables['recall'])} |"
        )
        lines += [
            "",
            f"Tabellen-Ebene: {tables['nicht_gezaehlt']} Plan-Kanten ohne Klemme/Adresse oder mit Enden, die die "
            "Tabellen nicht kennen, zaehlen nicht.",
        ]
    else:
        lines += ["", "Tabellen-Ebene: keine Tabellen im Ordner des Plans."]
    lines += ["", "## Abweichungen je Seite (Leitungen)", ""]
    if not deviations:
        lines.append("keine")
    for entry in deviations:
        parts = [f"fehlt {' - '.join(pair)}" for pair in entry["fehlend"]]
        parts += [f"fremd {' - '.join(pair)}" for pair in entry["fremd"]]
        lines.append(f"- Seite {entry['seite']}: " + "; ".join(parts))
    if foreign:
        lines += ["", "## Plan-Kanten, die die Tabellen nicht bestaetigen", ""]
        lines += [f"- {' - '.join(pair)}" for pair in foreign]
    return "\n".join(lines) + "\n"


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(
    argv: list[str] | None = None,
    measure_fn: Callable[[Path], tuple[list, float]] = measure,
    table_fn: Callable[[Path], object] = table_graph,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--gold", type=Path, required=True, help="Gold mit wires, z. B. eval/ingest_gold/fb01.json"
    )
    parser.add_argument("--doc", type=Path, help="Stromlaufplan; Standard: 'dokument' aus dem Gold")
    parser.add_argument(
        "--min-precision", type=float, default=0.0, help="Exit 1, wenn eine Precision darunter"
    )
    parser.add_argument("--out", type=Path, default=RESULTS, help="Ordner fuer JSON und Markdown")
    args = parser.parse_args(argv)

    document, gold = load_wires(args.gold)
    doc = args.doc or ROOT / document
    edges, seconds = measure_fn(doc)
    found = by_page(edges)
    wires, deviations = compare_wires(gold, by_page(e for e in edges if e.via == "leitung"))
    graph = table_fn(doc)
    tables, foreign = (None, [])
    if graph is not None:
        tables, foreign = compare_tables(found, *table_pairs(graph))
    failures = gate_failures(wires, tables, args.min_precision) if args.min_precision > 0 else []
    herkunft: dict[str, int] = {}
    for edge in edges:
        herkunft[edge.via] = herkunft.get(edge.via, 0) + 1
    summary = {
        "gold": _relative(args.gold),
        "dokument": _relative(doc),
        "kanten": len(edges),
        "gerichtet": sum(1 for edge in edges if edge.directed),
        "herkunft": dict(sorted(herkunft.items())),
        "sekunden": round(seconds, 2),
        "leitungen": wires,
        "tabellen": tables,
        "gate": {"min": args.min_precision, "ok": not failures, "verfehlt": failures},
    }
    out = evallib.save_result(
        args.out / f"plan_graph_{args.gold.stem}_{evallib.run_id()}.json",
        summary,
        deviations,
    )
    markdown = render_markdown(args.gold.stem, summary, deviations, foreign)
    out.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Ergebnis: {out}")
    if failures:
        print("Gate verfehlt: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
