"""Seitentitel und Stuecklistenseiten einer Schaltplan-PDF (app/ingestion/page_titles.py), Issue #39."""

from pathlib import Path

import pytest

from app.ingestion.docling_parser import ParsedPage
from app.ingestion.page_titles import is_parts_list, page_titles

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
QET = Path(__file__).resolve().parents[2] / "testdata" / "qelectrotech" / "QET_Beispielprojekt_industrial_50S.pdf"


def _page(number: int, *lines: str) -> ParsedPage:
    return ParsedPage(page=number, markdown="", raw_text="\n".join(lines))


def test_titel_aus_folio_liste_und_schriftfeld():
    """QET-Stil: Folio-Liste "4 Mains Power Supply ..." und der Titel steht als eigene Zeile auf der Seite."""
    pages = [
        _page(1, "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18", "References Page", "Folio : 1"),
        _page(2, "Folio list 1", "4 Mains Power Supply IM -IGC 1.0 01/09/2018",
              "6 Emergency Stop Circuit IM -IGC 1.0 01/09/2018", "41 Nomenclature IM -IGC 1.0 21/06/2020"),
        _page(4, "DATE 01/09/2018", "Mains Power Supply", "Example project", "4Q1 80A"),
        _page(6, "Emergency Stop Circuit", "6KE1"),
        _page(7, "irgendwas ohne Eintrag in der Liste"),
        _page(41, "Nomenclature", "4 Mains Power Supply 4Q1 80A"),
    ]
    titles, parts = page_titles(pages)
    assert titles == {4: "Mains Power Supply", 6: "Emergency Stop Circuit", 41: "Nomenclature"}
    assert parts == {41}


def test_titel_aus_inhaltsverzeichnis_mit_blatt_in_eigener_zeile():
    """FB-01-Stil: "Blatt 2" und der Titel stehen im Inhaltsverzeichnis untereinander."""
    pages = [
        _page(1, "Inhaltsverzeichnis", "Blatt 2", "Netzeinspeisung 400 V und Steuerspannung 24 V DC",
              "Blatt 3", "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)"),
        _page(2, "L1", "Netzeinspeisung 400 V und Steuerspannung 24 V DC", "Blatt 2 / 7"),
        _page(3, "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)"),
    ]
    titles, parts = page_titles(pages)
    assert titles == {
        2: "Netzeinspeisung 400 V und Steuerspannung 24 V DC",
        3: "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)",
    }
    assert parts == set()


def test_stuecklistenseite_auch_ohne_inhaltsverzeichnis():
    pages = [_page(1, "Stromlaufplan"), _page(2, "Stueckliste", "-K1 Schuetz"), _page(3, "Parts List", "4Q1")]
    titles, parts = page_titles(pages)
    assert parts == {2, 3}
    assert titles == {2: "Stueckliste", 3: "Parts List"}


def test_is_parts_list():
    assert all(is_parts_list(t) for t in ("Nomenclature", "Stückliste", "Artikelstueckliste", "Parts list", "Bill of Materials", "Bauteilliste"))
    assert not any(is_parts_list(t) for t in ("Mains Power Supply", "", "Stueckzahl", "Klemmenplan -X3"))


def test_echte_fb01_pdf_bekommt_ihre_blatttitel():
    from app.ingestion.docling_parser import pdf_raw_text

    raw = pdf_raw_text(EXAMPLE)
    titles, parts = page_titles([ParsedPage(page=no, markdown="", raw_text=text) for no, text in sorted(raw.items())])
    assert titles[2] == "Netzeinspeisung 400 V und Steuerspannung 24 V DC"
    assert titles[4] == "Not-Halt-Kreis und Bedientaster"
    assert titles[7] == "Klemmenplan -X3 und -X4"
    assert parts == set()


def test_inhaltsverzeichnis_nennt_blaetter_nicht_seiten():
    """Issue #67: Mit Deckblatt und Inhaltsverzeichnis vorne ist Blatt 1 die Seite 3."""
    pages = [
        _page(1, "Stromlaufplan", "Deckblatt"),
        _page(2, "Inhaltsverzeichnis", "1 Einspeisung 400 V 2026-09", "2 Steuerspannung 24 V DC 2026-09"),
        _page(3, "Einspeisung 400 V"),
        _page(4, "Steuerspannung 24 V DC"),
    ]
    titles, parts = page_titles(pages, sheet_of={3: 1, 4: 2})
    assert titles == {3: "Einspeisung 400 V", 4: "Steuerspannung 24 V DC"}


SCHRIFTFELD = Path(__file__).resolve().parents[2] / "examples" / "schriftfeld"
SHEET_TITLES = ["Einspeisung 400 V", "Steuerspannung 24 V DC", "Motorsteuerung Band", "Not-Halt-Kreis", "SPS-Eingaenge"]


@pytest.mark.parametrize(
    "name",
    ["blatt_schraegstrich.pdf", "blatt_von.pdf", "bl_punkt.pdf", "sheet_of.pdf", "getrennte_felder.pdf",
     "eplan_seitenname.pdf", "luecke.pdf"],
)
def test_schriftfeld_fixtures_bekommen_die_titel_ihrer_blaetter(name):
    from app.ingestion.docling_parser import pdf_raw_text
    from app.ingestion.pdf_layout import sheet_map

    path = SCHRIFTFELD / name
    raw = pdf_raw_text(path)
    pages = [ParsedPage(page=no, markdown="", raw_text=text) for no, text in sorted(raw.items())]
    titles, parts = page_titles(pages, sheet_of=sheet_map(path).page_sheets)
    assert titles == dict(enumerate(SHEET_TITLES, start=3))
    assert parts == set()


@pytest.mark.skipif(not QET.exists(), reason="QElectroTech-Testdaten liegen nur lokal (testdata/qelectrotech)")
def test_echte_qet_pdf_bekommt_folio_titel_und_stuecklistenseiten():
    from app.ingestion.docling_parser import pdf_raw_text

    raw = pdf_raw_text(QET)
    titles, parts = page_titles([ParsedPage(page=no, markdown="", raw_text=text) for no, text in sorted(raw.items())])
    assert titles[4] == "Mains Power Supply"
    assert titles[9] == "V1 Gate Control Circuit"
    assert titles[33] == "TB1 Terminal Bord"
    assert 41 in parts and 50 in parts and 9 not in parts
