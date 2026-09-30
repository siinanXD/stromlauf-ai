"""Dokumenttyp aus dem Inhalt: alle 18 Beispieldateien, Dateiname als Rueckfall, Fliesstext."""

from pathlib import Path

import pytest

from app.ingestion.doctype import detect, filename_doc_type, guess_doc_type, sample_text
from app.models import DocType

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
EXPECTED = {
    "01_Stromlaufplan": DocType.SCHEMATIC,
    "02_Stueckliste": DocType.BOM,
    "03_Klemmenplan": DocType.TERMINAL_PLAN,
    "04_SPS_Programm": DocType.PLC_PROGRAM,
    "05_Symboltabelle": DocType.PLC_SYMBOLS,
    "06_Betriebsanleitung": DocType.MANUAL,
}
FILES = sorted(
    path
    for folder in ("foerderband", "umroller", "aufrollung")
    for path in (EXAMPLES / folder).iterdir()
    if path.name[:3] in {"01_", "02_", "03_", "04_", "05_", "06_"} and path.suffix != ".png"
)


@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_example_files_by_content_only(path: Path):
    expected = EXPECTED[path.name[: path.name.rindex("_")]]
    found = guess_doc_type(sample_text(path))
    assert found.doc_type == expected, f"{path.name}: {found}"
    assert found.confidence >= 0.5
    assert found.reason


def test_detect_prefers_suffix_then_content_then_filename(tmp_path: Path):
    assert detect("x.awl").doc_type == DocType.PLC_PROGRAM
    assert detect("x.sdf").source == "suffix"
    plan = tmp_path / "4711_E_Rev3.csv"
    plan.write_text("Klemmleiste;Klemme;Ziel intern;Ziel extern\n-X1;-X1:1;-A1:1;-S1:13\n", encoding="utf-8")
    found = detect(plan.name, plan)
    assert (found.doc_type, found.source) == (DocType.TERMINAL_PLAN, "content")
    assert "Kopfzeile" in found.reason
    prose = tmp_path / "Handbuch_Presse.txt"
    prose.write_text("Hallo.\n", encoding="utf-8")
    found = detect(prose.name, prose)
    assert (found.doc_type, found.source) == (DocType.MANUAL, "filename")
    assert detect("scan_0815.pdf").doc_type == DocType.OTHER


def test_filename_hints():
    assert filename_doc_type("Anlage_Stueckliste_v2.xlsx") == DocType.BOM
    assert filename_doc_type("Symboltabelle.csv") == DocType.PLC_SYMBOLS
    assert filename_doc_type("4711.pdf") is None


def test_manual_beats_bom_when_manual_mentions_parts_list():
    text = "# Betriebsanleitung Presse P7\n\nZugehoerige Dokumente: Stueckliste P7, Klemmenplan P7.\n\n## Wartung\n\nVor der Inbetriebnahme Sicherheitshinweise lesen. " * 2
    assert guess_doc_type(text).doc_type == DocType.MANUAL


def test_unknown_text_stays_other():
    found = guess_doc_type("Protokoll vom Montag\nAnwesend: alle\n")
    assert found.doc_type == DocType.OTHER
    assert guess_doc_type("   ").source == "none"


QET_SAMPLE = """1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18
A
B
C
DATE 21/06/2020
References Page
Example project
Folio : 1
QET 0.8 Intake Gate Control Electrical Cabinet
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18
DATE
Folio list 1
Folio : 2
4 Mains Power Supply IM -IGC 1.0 01/09/2018
5 Auxiliary Power Supply IM -IGC 1.0 01/09/2018
6 Emergency Stop Circuit IM -IGC 1.0 01/09/2018
33 TB1 Terminal Bord IM -IGC 1.0 01/09/2018
41 Nomenclature IM -IGC 1.0 21/06/2020
"""


def test_englischer_stromlaufplan_mit_folio_schriftfeld():
    """Issue #39: QElectroTech-/englische Exporte haben "Folio : n" und ein Raster 1..18 statt "Blatt n / m"."""
    found = guess_doc_type(QET_SAMPLE)
    assert found.doc_type == DocType.SCHEMATIC, found
    assert "Folio" in found.reason and found.confidence >= 0.5


def test_englische_stueckliste_heisst_nomenclature_oder_parts_list():
    for title in ("Nomenclature", "Parts List", "Bill of Materials"):
        text = chr(10).join([title, "Folio Title Label Designation Manufacturer Qty", "4 Mains Power Supply 4Q1 80A Schneider Electric 1"])
        found = guess_doc_type(text)
        assert found.doc_type == DocType.BOM, (title, found)

QET_PDF = Path(__file__).resolve().parents[2] / "testdata" / "qelectrotech" / "QET_Beispielprojekt_industrial_50S.pdf"


@pytest.mark.skipif(not QET_PDF.exists(), reason="QElectroTech-Testdaten liegen nur lokal")
def test_echte_qet_pdf_wird_als_stromlaufplan_erkannt():
    found = detect(QET_PDF.name, QET_PDF)
    assert found.doc_type == DocType.SCHEMATIC and found.source == "content", found


TITLE_BLOCKS = sorted((EXAMPLES / "schriftfeld").glob("*.pdf"))


@pytest.mark.parametrize("path", TITLE_BLOCKS, ids=[p.name for p in TITLE_BLOCKS])
def test_schriftfeld_fixtures_sind_stromlaufplaene_am_inhalt(path: Path):
    """Issue #67: Deckblatt und Inhaltsverzeichnis vorne aendern den erkannten Typ nicht."""
    found = guess_doc_type(sample_text(path))
    assert found.doc_type == DocType.SCHEMATIC, found


SCAN_PDF = EXAMPLES / "scan" / "01_Stromlaufplan_FB-01_scan.pdf"


def test_voll_scan_meldet_scan_und_nimmt_den_typ_aus_dem_dateinamen():
    """Issue #64: leere Textprobe eines PDFs mit Seiten ist ein Scan, kein 'nicht erkannt'."""
    found = detect(SCAN_PDF.name, SCAN_PDF)
    assert (found.doc_type, found.source) == (DocType.SCHEMATIC, "filename")
    assert found.reason == f"Scan (keine Textebene); Typ aus Dateiname „{SCAN_PDF.name}“"


def test_scan_ohne_sprechenden_namen_bleibt_sonstiges_mit_scan_hinweis(tmp_path: Path):
    copy = tmp_path / "4711.pdf"
    copy.write_bytes(SCAN_PDF.read_bytes())
    found = detect(copy.name, copy)
    assert (found.doc_type, found.source, found.reason) == (
        DocType.OTHER,
        "content",
        "Scan (keine Textebene)",
    )


def test_teilscan_mit_textseiten_vorne_wird_am_inhalt_erkannt():
    partial = EXAMPLES / "scan" / "01_Stromlaufplan_FB-01_teilscan.pdf"
    found = detect(partial.name, partial)
    assert (found.doc_type, found.source) == (DocType.SCHEMATIC, "content"), found
