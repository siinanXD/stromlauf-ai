"""JSON fuer die Figma-Vorlagen (scripts/figma_json.py), Offline-Weg gegen FB-01: ohne Backend, Datenbank, Modell
und ohne Docling (der Test liest PDF-Rohtext und Tabellen als Klartext, wie test_page_titles.py)."""

import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest

from app.ingestion.awl_parser import read_text
from app.ingestion.docling_parser import ParsedPage, pdf_raw_text

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("figma_json", ROOT / "scripts" / "figma_json.py")
figma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(figma)

MELDUNG = "Störung Motorschutz Förderband"
# Antworttext aus dem Eintrag E-F2 der Fehlerliste (scripts/load_example.py), Belege aus seinem doc_ref
ANTWORT = (
    "E-F2: Motorschutz -F2 ausgeloest (E0.2 = 0) [[01_Stromlaufplan_FB-01.pdf|Blatt 3]]. -F2 pruefen, "
    "Motorstrom -M1 messen (Nennstrom 3,5 A). Nach Abkuehlen einschalten, mit -S1 quittieren "
    "[[06_Betriebsanleitung_FB-01.md|Kap. 6]]."
)
OFFLINE = ["--offline", "examples/foerderband", "--maschine", "Foerderband FB-01"]


def _ohne_docling(path: Path) -> list[ParsedPage]:
    if path.suffix.lower() == ".pdf":
        raw = pdf_raw_text(path)
        return [ParsedPage(page=no, markdown="", raw_text=text) for no, text in raw.items()]
    if path.suffix.lower() == ".xlsx":
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            lines = [
                " | ".join("" if cell is None else str(cell) for cell in row)
                for row in workbook.active.iter_rows(values_only=True)
            ]
        finally:
            workbook.close()
        return [ParsedPage(page=None, markdown="\n".join(lines))]
    return [ParsedPage(page=None, markdown=read_text(path))]


@pytest.fixture
def offline(tmp_path, monkeypatch):
    from app.ingestion import pipeline, plan_edges

    monkeypatch.setattr(pipeline, "parse_document", _ohne_docling)
    # Leitungen frisch aus dem Plan, kein Modelllauf aus einem lokalen Cache
    monkeypatch.setattr(plan_edges, "_cache_dir", lambda: tmp_path / "plan_cache")

    def run(*args: str) -> dict:
        out = tmp_path / "vorlage.json"
        assert figma.main([*args, *OFFLINE, "--out", str(out)]) == 0
        return json.loads(out.read_text(encoding="utf-8"))

    return run


def _main_path(signal: dict) -> list[str]:
    main = sorted((node for node in signal["nodes"] if node["main"]), key=lambda n: n["order"])
    return [node["id"] for node in main]


def test_stoerfall_antwort_fb01_offline(offline):
    data = offline("--vorlage", "stoerfall-antwort", "--meldung", MELDUNG, "--antwort", ANTWORT)

    assert figma.validate(data) == [] and figma.validate(data, use_jsonschema=False) == []
    assert data["frage"] == MELDUNG and data["antwort"] == ANTWORT
    assert "E-F2" in [fault["code"] for fault in data["fault_hits"]["faults"]]
    assert data["meta"]["referenced_tags"][0] == "-F2"
    assert data["meta"]["citations_valid"]["total"] == 2
    # Signalweg des ersten verfolgbaren Bauteils der Antwort, wie meta.signal_start
    path = _main_path(data["signal"])
    assert data["signal"]["start"] == "-F2" and path[0] == "-F2" and path[-1] == "-H2"


def test_signalweg_und_stoerfaelle_fb01_offline(offline):
    signal = offline("--vorlage", "signalweg", "--tag", "-F2")  # Wert mit Minus ohne "="
    assert figma.validate(signal) == []
    path = _main_path(signal["signal"])
    assert path[0] == "-F2" and path[-1] == "-H2"

    incidents = offline("--vorlage", "stoerfaelle", "--meldung", MELDUNG)
    assert figma.validate(incidents) == [] and incidents["ort"] == "Halle 1 (Beispiel)"
    assert [c["title"] for c in incidents["conversations"]] == [MELDUNG]


def test_eingebaute_pruefung_meldet_fehlende_felder_und_falsche_typen():
    errors = figma.validate({"vorlage": "signalweg", "version": 1}, use_jsonschema=False)
    assert errors == ["(oben): Feld maschine fehlt", "(oben): Feld signal fehlt"]
    errors = figma.validate(
        {
            "vorlage": "stoerfaelle",
            "version": 2,
            "maschine": "FB-01",
            "ort": "",
            "conversations": [{}],
        },
        use_jsonschema=False,
    )
    assert "version: erwartet 1" in errors and "conversations/0: Feld id fehlt" in errors
    assert figma.validate({"vorlage": "galerie"})[0].startswith("vorlage: unbekannt")


@pytest.mark.parametrize("path", sorted((ROOT / "design" / "figma" / "beispiele").glob("*.json")))
def test_beispiele_passen_zum_schema(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["vorlage"] == path.stem and data["version"] == 1
    assert figma.validate(data) == [] and figma.validate(data, use_jsonschema=False) == []
