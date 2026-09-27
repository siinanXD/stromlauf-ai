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
