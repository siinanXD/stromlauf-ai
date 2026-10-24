import json
import re
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.ingestion.awl_parser import read_text
from app.ingestion.plc_blocks import SCHEMA_PATH, SymbolTable, parse_plc_source
from app.sps.graph import build_graph, to_json, to_mermaid
from app.sps.graph.export import write_json

ROOT = Path(__file__).resolve().parents[2]
FOERDERBAND = ROOT / "examples" / "foerderband"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def foerderband_text() -> tuple[str, SymbolTable]:
    return (read_text(next(FOERDERBAND.glob("04_*.awl"))),
            SymbolTable.from_text(read_text(next(FOERDERBAND.glob("05_*.sdf")))))


@pytest.fixture(scope="module")
def fg():
    text, symbols = foerderband_text()
    program = parse_plc_source(text, symbols)
    VALIDATOR.validate(program.to_dict())
    return build_graph(program)


def ids(reach):
    return {r["id"] for r in reach}


def test_upstream_a40_sind_genau_die_geber(fg):
    # Sensoren und Taster, die A4.0 (Schuetz -K1) im Programm beeinflussen: -S1, -S2, -F2, -K3, -B1, -B2
    inputs = {r["id"] for r in fg.upstream("A 4.0") if r["kind"] == "input"}
    assert inputs == {"E0.0", "E0.1", "E0.2", "E0.3", "E0.4", "E0.5"}
    # Enden der Kette: dazu nur der Wartungsschalter M20.0 vom Bedienpanel
    assert ids(fg.sources("A4.0")) == inputs | {"M20.0"}
    # Schreibweisen: Absolutadresse, englisch, Symbolname
    assert fg.resolve("A 4.0") == fg.resolve("Q4.0") == fg.resolve("K1_Vorwaerts") == "A4.0"


def test_upstream_mit_tiefe(fg):
    first = fg.upstream("A4.0", depth=1)
    assert ids(first) == {"FB 10:Vorwaerts"}
    second = {r["id"]: r["depth"] for r in fg.upstream("A4.0", depth=2)}
    assert second["FB 10:Freigabe"] == 2 and second["FB 10:Rueckwaerts"] == 2 and "E0.0" not in second
    assert fg.upstream("A4.0", depth=0) == []


def test_downstream(fg):
    # Start (E0.0) wirkt auf Freigabe, Schuetz, Betriebsleuchte und ueber die Stoerung bis zur Sammelstoerung
    down = ids(fg.downstream("E0.0"))
    assert {"A4.0", "A4.1", "A4.2", "A4.3", "M10.0"} <= down
    assert "E0.1" not in down
    # M10.0 (Sammelstoerung) ist ein Blatt
    assert fg.downstream("M10.0") == []


def test_logik_der_kanten(fg):
    edge = fg.graph.edges["FB 10:Start", "FB 10:Freigabe"]
    assert edge["kinds"] == ["assign"] and edge["logic"] == ["ODER"] and edge["where"] == ["FB 10 NW 1"]
    assert fg.graph.edges["FB 10:Stop", "FB 10:Freigabe"]["logic"] == ["UND"]
    assert fg.graph.edges["FB 10:Stoerung", "FB 10:Freigabe"]["logic"] == ["UND NICHT"]
    # Setzen/Ruecksetzen und Timer
    assert "set" in fg.graph.edges["FB 10:MSS_OK", "FB 10:Stoerung"]["kinds"]
    assert "reset" in fg.graph.edges["FB 10:MSS_OK", "FB 10:Stoerung"]["kinds"]
    assert "timer" in fg.graph.edges["FB 10:LS_Einlauf", "T5"]["kinds"]
    assert fg.graph.nodes["T5"]["kind"] == "timer" and fg.graph.nodes["T5"]["name"] == "T_Blockade"
    # Flanke und Zaehlen
    assert fg.graph.edges["FB 10:LS_Auslauf", "FB 10:Flanke_Auslauf"]["kinds"] == ["edge"]


def test_aufruf_loest_parameter_auf(fg):
    g = fg.graph
    assert g.edges["E0.0", "FB 10:Start"]["kinds"] == ["param"]
    assert g.edges["M20.0", "FB 10:Richtung_Rueck"]["kinds"] == ["param"]
    # Ausgangsparameter laufen vom Baustein zum Aufrufer
    assert g.has_edge("FB 10:Vorwaerts", "A4.0") and not g.has_edge("A4.0", "FB 10:Vorwaerts")
    assert g.has_edge("block:OB 1", "block:FB 10") and g.edges["block:OB 1", "block:FB 10"]["kinds"] == ["call"]
    # Aufrufkanten sind kein Signalfluss
    assert "block:OB 1" not in ids(fg.upstream("A4.0"))
    # A4.3 wird im naechsten Netzwerk gelesen und in M10.0 gespiegelt
    assert g.has_edge("A4.3", "M10.0")


def test_unbekannter_operand(fg):
    with pytest.raises(KeyError):
        fg.upstream("E9.9")


def test_scl_ausgangsparameter():
    text = (
        'ORGANIZATION_BLOCK "Main"\nBEGIN\n'
        '   "FB_Motor_DB"(Start := "Taster", Ready => #Bereit);\n   "Lampe" := #Bereit;\n'
        'END_ORGANIZATION_BLOCK\n'
    )
    scl = build_graph(parse_plc_source(text, filename="x.scl"))
    # Ausgang des (unbekannten) Bausteins -> Bereit -> Lampe; Taster -> Baustein
    assert ids(scl.upstream("Lampe")) == {"Main:Bereit", "block:FB_Motor_DB", "Taster"}
    assert ids(scl.downstream("Taster")) == {"block:FB_Motor_DB", "Main:Bereit", "Lampe"}


def test_json_export(fg, tmp_path):
    data = to_json(fg)
    assert data["version"] == 1
    node_ids = [n["id"] for n in data["nodes"]]
    assert node_ids == sorted(node_ids) and "A4.0" in node_ids
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in data["edges"])
    out = tmp_path / "graph.json"
    write_json(fg, out)
    assert json.loads(out.read_text(encoding="utf-8")) == data


def test_mermaid_klein(fg):
    text = to_mermaid(fg)
    nodes = re.findall(r'^\s+(n\d+)[\[(]', text, re.M)
    assert text.startswith("flowchart LR") and 0 < len(nodes) <= 50
    assert '"K1_Vorwaerts (A4.0)"' in text and "Teilgraph" not in text
    assert "block:" not in text and "FB 10: Vorwaerts" in text


def test_mermaid_teilgraph_hoechstens_50_knoten():
    text, symbols = foerderband_text()
    big = "\n".join(
        text.replace("FB 10", f"FB {10 + i}").replace("DB 10", f"DB {10 + i}").replace("OB 1", f"OB {1 + i}")
        for i in range(6)
    )
    graph = build_graph(parse_plc_source(big, symbols))
    total = len([n for n, d in graph.graph.nodes(data=True) if d["kind"] != "block"])
    assert total > 50
    for view in (to_mermaid(graph), to_mermaid(graph, focus="A4.0", max_nodes=20)):
        count = len(re.findall(r'^\s+n\d+[\[(]', view, re.M))
        assert count in (20, 50)
        assert re.search(rf"%% Teilgraph.*: {count} von \d+ Knoten", view)
    # Fokus bleibt in der Ansicht, die naechsten Knoten zuerst
    focused = to_mermaid(graph, focus="A4.0", max_nodes=20)
    assert "classDef focus" in focused and '"K1_Vorwaerts (A4.0)"' in focused and '"FB 10: Vorwaerts"' in focused


def test_2000_zeilen_unter_3_sekunden():
    text, symbols = foerderband_text()
    lines = len(text.splitlines())
    copies = []
    for i in range(2000 // lines + 1):
        copies.append(text.replace("FB 10", f"FB {10 + i}").replace("DB 10", f"DB {10 + i}")
                      .replace("OB 1", f"OB {1 + i}"))
    big = "\n".join(copies)
    assert len(big.splitlines()) >= 2000
    program = parse_plc_source(big, symbols)
    start = time.perf_counter()
    graph = build_graph(program)
    to_json(graph)
    to_mermaid(graph, focus="A4.0")
    assert time.perf_counter() - start < 3
    assert graph.graph.number_of_nodes() > 100
