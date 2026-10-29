"""Hauptweg in festen Spalten (Stoerfall-Arbeitsflaeche, Spur A4), gegen den Beispielgraphen FB-01."""

import csv
from pathlib import Path

import openpyxl
from test_signal_graph import fb01_graph

from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.plan_edges import PlanEdge
from app.ingestion.signal_graph import Graph, add_plan_edges, build_graph
from app.ingestion.signal_view import COLUMNS, main_view

UR01 = Path(__file__).resolve().parents[2] / "examples" / "umroller"


def ur01_graph() -> Graph:
    with (UR01 / "03_Klemmenplan_UR-01.csv").open(encoding="utf-8-sig") as handle:
        terminal_rows = list(csv.reader(handle, delimiter=";"))
    sheet = openpyxl.load_workbook(UR01 / "02_Stueckliste_UR-01.xlsx").active
    bom_rows = [
        (row[0], row[1], row[5])
        for row in sheet.iter_rows(values_only=True)
        if isinstance(row[0], str) and row[0].startswith("-") and len(row) > 5
    ]
    symbols = parse_symbol_table(read_text(UR01 / "05_Symboltabelle_UR-01.sdf"))
    return build_graph(
        terminal_rows, bom_rows, symbols, read_text(UR01 / "04_SPS_Programm_UR-01.awl")
    )


def _main(view: dict) -> list[dict]:
    return sorted((node for node in view["nodes"] if node["main"]), key=lambda node: node["order"])


def _edge(view: dict, source: str, target: str) -> dict:
    return next(e for e in view["edges"] if (e["source"], e["target"]) == (source, target))


def test_k1_spalten_in_vertragsreihenfolge():
    view = main_view(fb01_graph(), "-K1")
    main = _main(view)
    assert [node["id"] for node in main] == [
        "M20.0",
        "FB 10/NW2",
        "A4.0",
        "-X3:9",
        "-K1",
        "-X4:U",
        "-M1",
    ]
    assert [node["column"] for node in main] == [
        "programm",
        "programm",
        "sps_ausgang",
        "klemme_nach",
        "schaltgeraet",
        "klemme_nach",
        "verbraucher",
    ]
    assert view["columns"] == [
        "programm",
        "sps_ausgang",
        "klemme_nach",
        "schaltgeraet",
        "verbraucher",
    ]
    assert view["columns"] == [column for column in COLUMNS if column in view["columns"]]
    assert [node["order"] for node in main] == list(range(7)) and view["start"] == "-K1"


def test_vom_taster_an_alle_spalten_vor_dem_programm():
    view = main_view(fb01_graph(), "-S1")
    assert [node["id"] for node in _main(view)][:3] == ["-S1", "-X3:1", "E0.0"]
    assert view["columns"] == [
        "feld",
        "klemme_vor",
        "sps_eingang",
        "programm",
        "sps_ausgang",
        "klemme_nach",
        "schaltgeraet",
        "verbraucher",
    ]


def test_pins_stehen_an_kanten_kein_knoten_ist_ein_anschluss():
    view = main_view(fb01_graph(), "-K1")
    assert _edge(view, "-X3:9", "-K1")["pins"] == {"from": None, "to": "A1"}
    assert _edge(view, "-K1", "-X4:U")["pins"] == {"from": "2", "to": None}
    assert all(node["kind"] != "pin" for node in view["nodes"])
    assert not any(":A1" in node["id"] for node in view["nodes"])
    # wer einen Anschluss sucht, landet beim Geraet
    assert main_view(fb01_graph(), "-K1:A1")["start"] == "-K1"


def _tie(order: list[tuple[str, str]]) -> dict:
    """Zwei gleich kurze Wege rueckwaerts: A2 -> M1 -> X und A1 -> M2 -> X."""
    graph = Graph()
    for node_id in ("X", "M1", "M2", "A1", "A2", "Y"):
        graph.node(node_id, "variable")
    for source, target in order:
        graph.edge(source, target, "awl")
    return main_view(graph, "X")


def test_gleichstand_wird_reproduzierbar_aufgeloest():
    edges = [("A2", "M1"), ("M1", "X"), ("A1", "M2"), ("M2", "X"), ("X", "Y")]
    first = _tie(edges)
    # kleinste Folge der IDs ab dem Start (X, M1, A2), nicht das kleinste Ende
    assert [node["id"] for node in _main(first)] == ["A2", "M1", "X", "Y"]
    assert _tie(list(reversed(edges))) == first


def test_branches_zaehlt_nachbarn_abseits_des_hauptwegs_auch_ungerichtete():
    view = main_view(fb01_graph(), "-K1")
    branches = {node["id"]: node["branches"] for node in _main(view)}
    assert branches["-K1"] == 2 and branches["-X4:U"] == 1 and branches["-X3:9"] == 0
    children = {node["id"] for node in view["nodes"] if node["parent"] == "-K1"}
    assert children == {"-X4:V", "-X4:W"}
    assert all(
        node["column"] is None and node["order"] is None
        for node in view["nodes"]
        if not node["main"]
    )

    graph = add_plan_edges(
        fb01_graph(), [PlanEdge("-K1:13", "-X5:1", 3, "leitung", directed=False)]
    )
    view = main_view(graph, "-K1")
    assert {node["id"]: node["branches"] for node in _main(view)}["-K1"] == 3
    edge = _edge(view, "-K1", "-X5:1")
    assert edge["directed"] is False and edge["via"] == ["leitung"] and edge["pins"]["from"] == "13"


def test_ungerichtete_kante_kommt_nie_auf_den_hauptweg():
    graph = add_plan_edges(
        Graph(),
        [
            PlanEdge("-X1:1", "E0.0", 1, "leitung"),
            PlanEdge("-X1:1", "-X1:2", 1, "leitung", directed=False),
        ],
    )
    view = main_view(graph, "-X1:1")
    assert [node["id"] for node in _main(view)] == ["-X1:1", "E0.0"]
    assert [node["id"] for node in view["nodes"] if not node["main"]] == ["-X1:2"]
    assert view["columns"] == ["klemme_vor", "sps_eingang"]


def _ids(view: dict) -> list[str]:
    return [node["id"] for node in _main(view)]


def test_hauptweg_vom_taster_fuehrt_zum_motor_nicht_zur_stoerleuchte():
    """Issue #121: kuerzester Weg war S1 > E0.0 > NW4 > A4.3 > -X3:12 > -H2."""
    view = main_view(fb01_graph(), "-S1")
    ids = _ids(view)
    chain = ["E0.0", "FB 10/NW1", "FB 10/NW2", "A4.0", "-X3:9", "-K1", "-X4:U", "-M1"]
    assert [i for i in ids if i in chain] == chain and ids[-1] == "-M1"
    assert "-H2" not in ids
    # Die Leuchte bleibt erreichbar: A4.3 zweigt an NW1 ab und fuehrt ueber -X3:12 weiter zu -H2
    branch = next(n for n in view["nodes"] if n["id"] == "A4.3")
    assert not branch["main"] and branch["parent"] == "FB 10/NW1" and branch["branches"] >= 1


def test_verbraucher_gewinnt_vor_laengerer_meldeleuchte_und_merkerbit():
    """Kuerzer ist die Leuchte (1 Schritt) und das Merkerbit "M10.0" (kein Motor), der Motor braucht 3."""
    graph = Graph()
    for tag, kind in (
        ("-S1", "device"),
        ("-H1", "device"),
        ("M10.0", "address"),
        ("-X2:1", "terminal"),
        ("-K1", "device"),
        ("-M1", "device"),
    ):
        graph.node(tag, kind)
    for source, target in (
        ("-S1", "-H1"),
        ("-S1", "M10.0"),
        ("-S1", "-X2:1"),
        ("-X2:1", "-K1"),
        ("-K1", "-M1"),
    ):
        graph.edge(source, target, "awl")
    view = main_view(graph, "-S1")
    assert _ids(view) == ["-S1", "-X2:1", "-K1", "-M1"]
    assert {n["id"] for n in view["nodes"] if n["parent"] == "-S1"} == {"-H1", "M10.0"}


def test_ur01_hauptweg_endet_am_motor_nicht_an_der_leuchte():
    graph = ur01_graph()
    for tag in ("-S4", "-F7"):
        ids = _ids(main_view(graph, tag))
        assert ids[0] == tag and ids[-1].startswith("-M"), ids
        assert "-H1" not in ids


def test_sps_ausgang_fuehrt_ueber_seine_verdrahtung_zur_leuchte():
    """Review SIN-1189: Vom Ausgang A4.3 fuehrte der Hauptweg zurueck ins Programm (NW1) bis zum Motor -M1,
    obwohl A4.3 ueber -X3:12 die Stoerleuchte -H2 schaltet. Ein SPS-Ausgang geht vorwaerts ueber seine Verdrahtung."""
    ids = _ids(main_view(fb01_graph(), "A4.3"))
    assert ids[ids.index("A4.3"):] == ["A4.3", "-X3:12", "-H2"]
    # Der Weg vom Taster und vom Ausgang A4.0 bleibt beim Motor.
    assert _ids(main_view(fb01_graph(), "-S1"))[-1] == "-M1"
    assert _ids(main_view(fb01_graph(), "A4.0"))[-4:] == ["-X3:9", "-K1", "-X4:U", "-M1"]
