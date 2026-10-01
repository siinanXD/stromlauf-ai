"""Hauptweg in festen Spalten (Stoerfall-Arbeitsflaeche, Spur A4), gegen den Beispielgraphen FB-01."""

from app.ingestion.plan_edges import PlanEdge
from app.ingestion.signal_graph import Graph, add_plan_edges
from app.ingestion.signal_view import COLUMNS, main_view
from test_signal_graph import fb01_graph


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
