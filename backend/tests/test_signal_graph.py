import csv
from pathlib import Path

import openpyxl

from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.signal_graph import Graph, build_graph, signal_path

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
    """S12/S22 eines Sicherheitsrelais sind Eingaenge: Not-Halt -> Klemme -> Relais, nicht umgekehrt."""
    rows = [
        ["-X3", "-X3:40", "-K1:S12", "-S3:12 (Reihe: -S1, -S2, -S3)", "Not-Halt Kanal 1 Ende", "/7.2"],
        ["-X3", "-X3:39", "-K1:S11", "-S1:11", "Not-Halt Kanal 1 Beginn", "/7.2"],
    ]
    graph = build_graph(rows, [("-K1", "Sicherheitsrelais", "/7.2"), ("-S1", "Not-Halt", "/7.2"), ("-S3", "Not-Halt", "/7.2")], [], "")
    assert ("-S3", "-X3:40") in graph.edges and ("-X3:40", "-K1") in graph.edges
    assert ("-K1", "-X3:39") in graph.edges and ("-X3:39", "-S1") in graph.edges
