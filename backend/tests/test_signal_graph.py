import csv
from pathlib import Path

import openpyxl

from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.plan_edges import PlanEdge
from app.ingestion.signal_graph import Graph, add_plan_edges, build_graph, signal_path

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "foerderband"


def fb01_graph() -> Graph:
    with (EXAMPLE / "03_Klemmenplan_FB-01.csv").open(encoding="utf-8-sig") as handle:
        terminal_rows = list(csv.reader(handle, delimiter=";"))
    sheet = openpyxl.load_workbook(EXAMPLE / "02_Stueckliste_FB-01.xlsx").active
    bom_rows = [
        (row[0], row[1], row[5])
        for row in sheet.iter_rows(values_only=True)
        if isinstance(row[0], str) and row[0].startswith("-") and len(row) > 5
    ]
    symbols = parse_symbol_table(read_text(EXAMPLE / "05_Symboltabelle_FB-01.sdf"))
    awl = read_text(EXAMPLE / "04_SPS_Programm_FB-01.awl")
    return build_graph(terminal_rows, bom_rows, symbols, awl)


def levels(path: dict) -> dict[str, int]:
    return {node["id"]: node["level"] for node in path["nodes"]}


def test_start_button_path_reaches_motor_in_signal_order():
    path = signal_path(fb01_graph(), "-S1")
    level = levels(path)
    chain = ["-S1", "-X3:1", "E0.0", "A4.0", "-X3:9", "-K1", "-X4:U", "-M1"]
    assert all(tag in level for tag in chain), {tag: level.get(tag) for tag in chain}
    assert [level[t] for t in chain] == sorted(level[t] for t in chain)
    assert len({level[t] for t in chain}) == len(chain)  # streng steigend
    assert any(node["kind"] == "network" and 0 < node["level"] < level["A4.0"] for node in path["nodes"])


def test_path_contains_labels_and_refs_from_documents():
    nodes = {n["id"]: n for n in signal_path(fb01_graph(), "-S1")["nodes"]}
    assert nodes["-K1"]["label"] == "Schuetz Foerdermotor vorwaerts"
    assert nodes["-K1"]["ref"] == "/3.4"
    assert nodes["-X3:1"]["ref"] == "/5.3"
    assert any(n["kind"] == "network" and n["ref"].startswith("FB 10 NW") for n in nodes.values())


def test_upstream_of_motor_is_negative():
    level = levels(signal_path(fb01_graph(), "-M1"))
    assert level["-M1"] == 0 and level["-K1"] < 0 and level["-X4:U"] < 0


def test_supply_terminal_does_not_explode():
    path = signal_path(fb01_graph(), "-X2:2")
    assert path is None or len(path["nodes"]) < 40


def test_unknown_tag_and_empty_graph_give_none():
    assert signal_path(fb01_graph(), "-Z99") is None
    assert signal_path(build_graph([], [], [], ""), "-S1") is None


def test_lowercase_input_is_normalized():
    assert signal_path(fb01_graph(), "s1") is not None


def test_internal_variables_get_their_declaration_comment():
    nodes = {n["id"]: n for n in signal_path(fb01_graph(), "-S1")["nodes"]}
    assert nodes["FB 10#Freigabe"]["label"] == "Selbsthaltung Betrieb"


def test_every_bom_device_is_a_node_with_ref():
    graph = fb01_graph()
    assert graph.nodes["-Q1"].ref == "/2.2" and graph.nodes["-T1"].label.startswith("Netzteil")


def test_terminal_strips_x10_and_up_are_not_treated_as_supply():
    rows = [["-X10", "-X10:1", "-A1.1:1 (E0.0)", "-S1:13", "Start", "/5.3"]]
    path = signal_path(build_graph(rows, [], [], ""), "-S1")
    assert path is not None and "-X10:1" in {n["id"] for n in path["nodes"]}


def test_broken_files_do_not_raise(tmp_path):
    from app.api.signal import _graph

    bad_xlsx = tmp_path / "stueckliste.xlsx"
    bad_xlsx.write_bytes(b"kein zip")
    bad_csv = tmp_path / "klemmen.csv"
    bad_csv.write_text('Klemme;"' + "x" * 200_000 + "\n", encoding="utf-8")
    graph = _graph((("bom", str(bad_xlsx), 0.0), ("terminal_plan", str(bad_csv), 0.0)))
    assert graph.nodes == {}


def test_safety_relay_input_terminals_count_as_inputs():
    """S12/S22 eines Sicherheitsrelais sind Eingaenge: Not-Halt -> Klemme -> Relais, nicht umgekehrt. Die
    Not-Halt-Kontakte stehen seit #98 als eigene Knoten im Weg (Oeffner 11/12)."""
    rows = [
        ["-X3", "-X3:40", "-K1:S12", "-S3:12 (Reihe: -S1, -S2, -S3)", "Not-Halt Kanal 1 Ende", "/7.2"],
        ["-X3", "-X3:39", "-K1:S11", "-S1:11", "Not-Halt Kanal 1 Beginn", "/7.2"],
    ]
    graph = build_graph(rows, [("-K1", "Sicherheitsrelais", "/7.2"), ("-S1", "Not-Halt", "/7.2"), ("-S3", "Not-Halt", "/7.2")], [], "")
    assert {("-S3", "-S3:12"), ("-S3:12", "-X3:40"), ("-X3:40", "-K1")} <= graph.edges.keys()
    assert {("-K1", "-X3:39"), ("-X3:39", "-S1:11"), ("-S1:11", "-S1")} <= graph.edges.keys()
    assert ("-S3", "-X3:40") not in graph.edges


def test_weg_fuehrt_ueber_die_spule_zu_den_kontakten_desselben_schuetzes():
    """Issue #98: A4.0 schaltet die Spule -K1:A1, das Schuetz -K1 schliesst seine Hauptkontakte -K1:2/4/6."""
    graph = fb01_graph()
    level = levels(signal_path(graph, "A4.0"))
    chain = ["A4.0", "-X3:9", "-K1:A1", "-K1", "-K1:2", "-X4:U", "-M1"]
    assert all(tag in level for tag in chain), {tag: level.get(tag) for tag in chain}
    assert [level[t] for t in chain] == list(range(level["A4.0"], level["A4.0"] + len(chain)))
    coil, contact = graph.nodes["-K1:A1"], graph.nodes["-K1:2"]
    assert (coil.kind, coil.label, coil.ref) == ("pin", "Spule", "/6.3")
    assert (contact.kind, contact.label, contact.ref) == ("pin", "Hauptkontakt", "/3.5")


def test_kontakte_als_quelle_einer_klemme():
    """Taster-Schliesser -S1:13 meldet an E0.0, Freigabekontakt -K3:24 an E0.3, Meldekontakt -K3:32 schaltet -H3."""
    graph = fb01_graph()
    assert {("-S1", "-S1:13"), ("-S1:13", "-X3:1"), ("-X3:1", "E0.0")} <= graph.edges.keys()
    assert {("-K3", "-K3:24"), ("-K3:24", "-X3:4")} <= graph.edges.keys()
    assert {("-K3", "-K3:32"), ("-K3:32", "-X3:15"), ("-X3:15", "-H3")} <= graph.edges.keys()
    assert graph.nodes["-K3:32"].label == "Öffner" and graph.nodes["-S1:13"].label == "Schließer"


def test_anschluss_ohne_eigenen_knoten_startet_beim_geraet():
    """Wer "-K2:13" sucht, landet bei -K2, wenn der Plan diesen Kontakt nicht nennt."""
    assert signal_path(fb01_graph(), "-K2:13")["start"] == "-K2"


def test_weg_vom_sensor_bis_zum_motor_bleibt_vollstaendig():
    """Spule und Kontakt kosten je Schaltgeraet zwei Stufen; der Weg -B1 -> ... -> -M1 darf nicht abbrechen."""
    level = levels(signal_path(fb01_graph(), "-B1"))
    assert "-M1" in level and level["-M1"] > level["-K1"] > level["-X3:9"] > 0


# --- Herkunft und Kanten aus dem Stromlaufplan (Stoerfall-Arbeitsflaeche, Spur A3) ----------------


def test_kanten_nennen_ihre_herkunft_klemmenplan_und_awl():
    graph = fb01_graph()
    assert graph.edges[("-X3:1", "E0.0")] == {"klemmenplan"}
    awl = [(source, target) for source, target in graph.edges if target.startswith("FB 10/NW")]
    assert awl and all(graph.edges[edge] == {"awl"} for edge in awl)
    path = signal_path(graph, "-S1")
    edge = next(e for e in path["edges"] if (e["source"], e["target"]) == ("-X3:1", "E0.0"))
    assert edge["via"] == ["klemmenplan"] and edge["directed"] is True


def test_plan_kante_macht_reine_pdf_quelle_verfolgbar():
    """Nur ein Stromlaufplan, keine Tabellen: Taster -> Klemme -> Eingang aus den Leitungen."""
    graph = add_plan_edges(
        Graph(),
        [
            PlanEdge("-S1:14", "-X3:1", 4, "leitung"),
            PlanEdge("-X3:1", "E0.0", 5, "leitung"),
        ],
    )
    level = levels(signal_path(graph, "-S1"))
    assert level["-S1"] < level["-S1:14"] < level["-X3:1"] < level["E0.0"]
    assert graph.nodes["-S1:14"].kind == "pin" and graph.nodes["-S1:14"].label == "Schließer"
    assert graph.nodes["-X3:1"].ref == "S. 4" and graph.edges[("-S1", "-S1:14")] == {"leitung"}
    assert {e["via"][0] for e in signal_path(graph, "-S1")["edges"]} == {"leitung"}


def test_ungerichtete_kante_bestimmt_keine_ebene_und_tabelle_gibt_die_richtung():
    graph = add_plan_edges(
        Graph(),
        [PlanEdge("-X3:2", "-X3:1", 5, "leitung", directed=False), PlanEdge("-X3:1", "E0.0", 5, "leitung")],
    )
    assert ("-X3:1", "-X3:2") in graph.undirected
    path = signal_path(graph, "-X3:1")
    assert "-X3:2" not in levels(path)  # nur ueber die ungerichtete Kante erreichbar
    graph.edge("-X3:2", "-X3:1", "klemmenplan")  # die Tabelle kennt die Richtung
    assert graph.undirected == set() and graph.edges[("-X3:2", "-X3:1")] == {"leitung", "klemmenplan"}
    assert ("-X3:1", "-X3:2") not in graph.edges


def test_plan_kante_zu_bekannter_tabellenkante_ergaenzt_nur_die_herkunft():
    graph = add_plan_edges(fb01_graph(), [PlanEdge("-X3:1", "E0.0", 5, "leitung", directed=False)])
    assert graph.edges[("-X3:1", "E0.0")] == {"klemmenplan", "leitung"}
    assert ("-X3:1", "E0.0") not in graph.undirected
