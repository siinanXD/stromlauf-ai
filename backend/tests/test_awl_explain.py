"""SPS-Erklaerer: Klartext der AWL-Netzwerke und Rueckverfolgung eines Ausgangs gegen examples/foerderband/."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import awl
from app.db import get_session
from app.ingestion.awl_explain import explain_awl, resolve_output, why_not
from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.signal_graph import _address
from tests.test_signal_api import TABLES, _document, _Session
from tests.test_signal_graph import EXAMPLE, fb01_graph


def _symbols() -> dict[str, str]:
    rows = parse_symbol_table(read_text(EXAMPLE / "05_Symboltabelle_FB-01.sdf"))
    return {row["symbol"]: a for row in rows if (a := _address(row["address"]))}


def _networks() -> dict[str, dict]:
    explained = explain_awl(read_text(EXAMPLE / "04_SPS_Programm_FB-01.awl"), _symbols())
    return {item["id"]: item for item in explained}


def test_selbsthaltung_klartext_mit_und_oder_nicht_und_symbolen():
    text = " ".join(_networks()["FB 10/NW1"]["klartext"])
    assert text.startswith("Freigabe ist EIN, wenn ")
    assert "(Start (E0.0) ODER Freigabe)" in text
    assert " UND Stop (E0.1) UND MSS_OK (E0.2) UND NotHalt_OK (E0.3) UND NICHT Stoerung" in text


def test_verriegelung_und_setzen_rucksetzen():
    networks = _networks()
    assert networks["FB 10/NW2"]["klartext"] == [
        "Vorwaerts (A4.0) ist EIN, wenn Freigabe UND NICHT Richtung_Rueck (M20.0) UND NICHT Rueckwaerts (A4.1)."
    ]
    nw4 = networks["FB 10/NW4"]["klartext"]
    assert nw4[0].startswith("Stoerung (A4.3) wird gesetzt") and "NICHT MSS_OK" in nw4[0]
    assert nw4[1].startswith("Stoerung (A4.3) wird zurückgesetzt")


def test_zeit_flanke_und_aufruf():
    networks = _networks()
    assert any("Einschaltverzögerung (20 s)" in s for s in networks["FB 10/NW5"]["klartext"])
    assert "steigende Flanke von (LS_Auslauf (E0.5))" in networks["FB 10/NW7"]["klartext"][0]
    assert any(line.startswith("L ") for line in networks["FB 10/NW7"]["other"])
    assert networks["OB 1/NW1"]["klartext"][0].startswith("Ruft FB 10 mit Instanz DB 10 auf")


def test_rueckverfolgung_liefert_alle_eingaenge_mit_klemme():
    graph = fb01_graph()
    target = resolve_output(graph, _symbols(), "A 4.0")
    assert target == "A4.0"
    result = why_not(graph, list(_networks().values()), target)
    nw2 = next(n for n in result["networks"] if n["id"] == "FB 10/NW2")
    assert {i["id"] for i in nw2["inputs"]} == {"FB 10#Freigabe", "M20.0", "A4.1"}
    nw1 = next(n for n in result["networks"] if n["id"] == "FB 10/NW1")
    inputs = {i["id"]: i for i in nw1["inputs"]}
    assert {"E0.0", "E0.1", "E0.2", "E0.3", "A4.3", "FB 10#Freigabe"} <= set(inputs)
    assert (inputs["E0.0"]["terminal"], inputs["E0.0"]["device"]) == ("-X3:1", "-S1")
    assert all(inputs[a]["terminal"] for a in ("E0.0", "E0.1", "E0.2", "E0.3"))
    assert "FB 10/NW1" in next(i for i in nw2["inputs"] if i["id"] == "FB 10#Freigabe")["written_by"]
    assert result["target"]["terminal"] == "-X3:9"


def test_api_networks_und_why():
    documents = [_document(doc_type, name) for doc_type, name in TABLES.items()]
    app = FastAPI()
    app.include_router(awl.router)
    app.dependency_overrides[get_session] = lambda: _Session(documents)
    client = TestClient(app)
    assert len(client.get("/api/awl/networks", params={"source_id": "s"}).json()["networks"]) == 9
    why = client.get("/api/awl/why", params={"source_id": "s", "output": "A4.0"}).json()
    assert why["target"]["id"] == "A4.0" and why["networks"][0]["id"] == "FB 10/NW2"
    assert client.get("/api/awl/why", params={"source_id": "s", "output": "Q9.9"}).status_code == 404


def test_symbol_und_unbekannter_ausgang():
    graph = fb01_graph()
    assert resolve_output(graph, _symbols(), "Q9.9") is None
    assert Path(EXAMPLE / "04_SPS_Programm_FB-01.awl").exists()
