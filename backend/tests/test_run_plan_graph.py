"""Planleser-Benchmark (Stoerfall-Arbeitsflaeche, Spur A2): Zahlen an einem Mini-Gold exakt, ohne PDF und Datenbank."""

import importlib.util
import json
import re
from collections import namedtuple
from pathlib import Path

import pytest

from app.ingestion.signal_graph import Graph

ROOT = Path(__file__).resolve().parents[2]
Edge = namedtuple("Edge", "source target page via directed")


def _load(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_plan_graph = _load("run_plan_graph", ROOT / "eval")

WIRES = {"1": [["-S1:14", "-X3:1"], ["-X3:1", "E0.0"]], "2": [["-X3:9", "A4.0"]]}
FOUND = [
    Edge("-S1:14", "-X3:1", 1, "leitung", True),  # Treffer
    Edge("-X3:1", "E0.0", 1, "leitung", True),  # Treffer
    Edge("-X3:9", "-X3:10", 2, "leitung", False),  # fremd; fehlt: A4.0 - -X3:9
    Edge("-S2", "-X3:1", 3, "lage", True),  # fremd, Seite ohne Gold
]


def _table_graph() -> Graph:
    """Klemmenplan und AWL im Kleinen: Taster -> Klemme -> Eingang -> Netzwerk -> Ausgang -> Klemme -> Spule."""
    graph = Graph()
    for node_id, kind in (
        ("-S1", "device"),
        ("-S1:13", "pin"),
        ("-S2", "device"),
        ("-X3:1", "terminal"),
        ("E0.0", "address"),
        ("FB 10/NW1", "network"),
        ("A4.0", "address"),
        ("-X3:9", "terminal"),
        ("-K1:A1", "pin"),
        ("-K1", "device"),
    ):
        graph.node(node_id, kind)
    chain = ["-S1", "-S1:13", "-X3:1", "E0.0", "FB 10/NW1", "A4.0", "-X3:9", "-K1:A1", "-K1"]
    for source, target in zip(chain, chain[1:], strict=False):
        graph.edge(source, target)
    return graph


def _gold(tmp_path: Path) -> Path:
    path = tmp_path / "mini.json"
    path.write_text(
        json.dumps(
            {"dokument": "examples/x.pdf", "doc_type": "schematic", "seiten": {}, "wires": WIRES}
        ),
        encoding="utf-8",
    )
    return path


def test_leitungen_precision_recall_und_abweichungen_exakt():
    gold = {int(page): {frozenset(pair) for pair in pairs} for page, pairs in WIRES.items()}
    metrics, deviations = run_plan_graph.compare_wires(gold, run_plan_graph.by_page(FOUND))
    assert metrics == {"tp": 2, "fp": 2, "fn": 1, "precision": 0.5, "recall": pytest.approx(2 / 3)}
    assert deviations == [
        {"seite": 2, "fehlend": [["-X3:9", "A4.0"]], "fremd": [["-X3:10", "-X3:9"]]},
        {"seite": 3, "fehlend": [], "fremd": [["-S2", "-X3:1"]]},
    ]


def test_tabellen_zaehlen_nur_kanten_an_klemmen_und_adressen_die_die_tabellen_kennen():
    nodes, pairs = run_plan_graph.table_pairs(_table_graph())
    assert "FB 10/NW1" not in nodes and "-S1:13" not in nodes and "-S1" in nodes
    assert pairs == {
        frozenset(pair)
        for pair in (("-S1", "-X3:1"), ("-X3:1", "E0.0"), ("A4.0", "-X3:9"), ("-X3:9", "-K1"))
    }
    metrics, foreign = run_plan_graph.compare_tables(run_plan_graph.by_page(FOUND), nodes, pairs)
    # gezaehlt: -S1--X3:1 (Anschluss im Geraet), -X3:1--E0.0, -S2--X3:1; -X3:10 kennen die Tabellen nicht
    assert metrics == {
        "gezaehlt": 3,
        "nicht_gezaehlt": 1,
        "bestaetigt": 2,
        "precision": pytest.approx(2 / 3),
        "tabellenkanten": 4,
        "recall": 0.5,
    }
    assert foreign == [["-S2", "-X3:1"]]


def test_cli_schreibt_ergebnis_und_scheitert_unter_der_precision(tmp_path):
    gold = _gold(tmp_path)
    seen = []

    def fake_measure(doc: Path):
        seen.append(doc)
        return FOUND, 0.5

    args = ["--gold", str(gold), "--out", str(tmp_path)]
    assert (
        run_plan_graph.main(
            [*args, "--min-precision", "0.95"], fake_measure, lambda _doc: _table_graph()
        )
        == 1
    )
    assert seen == [ROOT / "examples" / "x.pdf"]
    result = json.loads(next(tmp_path.glob("plan_graph_mini_*.json")).read_text(encoding="utf-8"))
    summary = result["summary"]
    assert summary["kanten"] == 4 and summary["gerichtet"] == 3
    assert summary["herkunft"] == {"lage": 1, "leitung": 3}
    # Ebene 1 misst nur gezeichnete Leitungen: die Kante aus der Lage (Seite 3) zaehlt erst gegen die Tabellen
    assert summary["leitungen"] == {
        "tp": 2,
        "fp": 1,
        "fn": 1,
        "precision": pytest.approx(2 / 3),
        "recall": pytest.approx(2 / 3),
    }
    assert summary["gate"]["verfehlt"] == [
        "Leitungen: Precision 0.67 < 0.95",
        "Tabellen: Precision 0.67 < 0.95",
    ]
    markdown = next(tmp_path.glob("plan_graph_mini_*.md")).read_text(encoding="utf-8")
    assert "| Leitungen | 3 | 3 | 2 | 0.67 | 0.67 |" in markdown
    assert "| Tabellen | 4 | 3 | 2 | 0.67 | 0.50 |" in markdown
    assert (
        run_plan_graph.main(
            [*args, "--min-precision", "0.5"], fake_measure, lambda _doc: _table_graph()
        )
        == 0
    )


def test_ohne_gefundene_kante_scheitert_das_gate_ohne_tabellen_wird_nur_berichtet(tmp_path):
    args = ["--gold", str(_gold(tmp_path)), "--out", str(tmp_path), "--min-precision", "0.95"]
    assert run_plan_graph.main(args, lambda _doc: ([], 0.1), lambda _doc: None) == 1
    summary = json.loads(next(tmp_path.glob("plan_graph_mini_*.json")).read_text(encoding="utf-8"))[
        "summary"
    ]
    assert summary["tabellen"] is None
    assert summary["gate"]["verfehlt"] == ["Leitungen: keine Kante gefunden"]


@pytest.mark.parametrize("name", ["fb01", "ur01", "pm1_ar"])
def test_jedes_gold_hat_leitungen_und_steht_im_planleser_gate(name):
    document, pages = run_plan_graph.load_wires(ROOT / "eval" / "ingest_gold" / f"{name}.json")
    assert document.endswith(".pdf") and sum(len(pairs) for pairs in pages.values()) >= 30
    workflow = (ROOT / ".github" / "workflows" / "eval.yml").read_text(encoding="utf-8")
    assert re.search(
        rf"run_plan_graph\.py --gold eval/ingest_gold/{name}\.json --min-precision 0\.95", workflow
    )
