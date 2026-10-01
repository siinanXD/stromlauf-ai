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


def test_titel_aus_dem_schweizer_schriftfeld():
    """Issue #93: Der Blatttitel ist das Feld des Schriftfelds, das sich von Blatt zu Blatt aendert. Dokumentart,
    Anlage und Zeichner stehen auf jedem Blatt, das Datum ist ein Datum; Deckblatt und Inhaltsverzeichnis ohne
    Blattnummer bekommen keinen Titel."""
    from app.ingestion.pdf_layout import title_block_titles

    expected = dict(enumerate(SHEET_TITLES, start=3))
    assert title_block_titles(SCHRIFTFELD / "elektroschema.pdf") == expected


@pytest.mark.parametrize(
    "name",
    [
        "blatt_schraegstrich.pdf",
        "blatt_von.pdf",
        "bl_punkt.pdf",
        "sheet_of.pdf",
        "getrennte_felder.pdf",
        "eplan_seitenname.pdf",
    ],
)
def test_titel_aus_dem_schriftfeld_stimmen_mit_dem_inhaltsverzeichnis_ueberein(name):
    from app.ingestion.pdf_layout import title_block_titles

    assert title_block_titles(SCHRIFTFELD / name) == dict(enumerate(SHEET_TITLES, start=3))


_Line = tuple[str, float, float, float, float]


def _ocr_pdf(tmp_path: Path, pages: list[list[_Line]]) -> Path:
    """Leere Seiten mit unsichtbaren Zeilen (Text, links, rechts, oben, Hoehe; relativ, Ursprung oben links)."""
    import pypdfium2 as pdfium

    from app.ingestion.ocr import OcrLine, write_text_layer

    def ocr_line(text: str, x0: float, x1: float, top: float, height: float) -> OcrLine:
        return OcrLine(text, ((x0, top), (x1, top), (x1, top + height), (x0, top + height)), 0.99)

    src, out = tmp_path / "leer.pdf", tmp_path / "plan.pdf"
    pdf = pdfium.PdfDocument.new()
    for _ in pages:
        pdf.new_page(842, 595)
    pdf.save(src)
    pdf.close()
    lines = {no: [ocr_line(*line) for line in page] for no, page in enumerate(pages, start=1)}
    write_text_layer(src, out, lines)
    return out


def _fit(text: str, x0: float, top: float, height: float = 0.016) -> _Line:
    """Zeile so breit wie ihr Text, wie eine OCR-Box. In einer gedehnten Box ruecken Woerter bis an WORD_GAP
    auseinander, und je nach Schrift der Plattform wird ein Wort zum eigenen Feld (so geschehen unter Linux)."""
    return (text, x0, x0 + 0.4 * height * len(text), top, height)


def test_zeile_an_der_grenze_des_schriftfelds_zaehlt_ganz_oder_gar_nicht(tmp_path):
    """Schneidet die Obergrenze des Schriftfelds eine Zeile, ragen Grossbuchstaben und Oberlaengen darueber, die
    Kleinbuchstaben nicht. Wortreste wie "rennen" duerfen kein zweites Feld werden, sonst fehlt der Titel."""
    from app.ingestion.pdf_layout import title_block_titles

    sheets = [("Trennen", "Netzteil 24 V"), ("Verteilen", "Motor Band"), ("Pruefen", "Not-Halt")]
    pages = [
        [
            (f"Station {station}", 0.05, 0.30, 0.895, 0.05),
            _fit(title, 0.40, 0.93),
            ("Blatt", 0.80, 0.86, 0.93, 0.016),
            (str(sheet), 0.88, 0.90, 0.93, 0.016),
        ]
        for sheet, (station, title) in enumerate(sheets, start=1)
    ]
    expected = {1: "Netzteil 24 V", 2: "Motor Band", 3: "Not-Halt"}
    assert title_block_titles(_ocr_pdf(tmp_path, pages)) == expected


def test_inhaltsverzeichnis_und_stuecklistenzeile_gehen_dem_schriftfeld_vor():
    pages = [
        _page(1, "Inhaltsverzeichnis", "Blatt 3", "Einspeisung 400 V"),
        _page(3, "Einspeisung 400 V"),
        _page(4, "irgendwas"),
        _page(5, "Stueckliste", "-K1 Schuetz"),
    ]
    block = {3: "Einspeisung", 4: "Steuerung 24 V", 5: "Bauteile"}
    titles, parts = page_titles(pages, block_titles=block)
    assert titles == {3: "Einspeisung 400 V", 4: "Steuerung 24 V", 5: "Stueckliste"}
    assert parts == {5}


def test_pipeline_titel_aus_dem_schriftfeld_ohne_inhaltsverzeichnis(tmp_path, monkeypatch):
    """Drei Blaetter ohne Inhaltsverzeichnis, Schriftfeld als Kastenreihe wie im Schweizer Elektroschema."""
    from app.ingestion import pipeline
    from app.ingestion.docling_parser import pdf_raw_text

    titles = ["Uebersicht SPS", "Netzteil 24 V", "Eingaenge Band 2"]
    dates = ["4. März 2019", "12. Oktober 2018", "07. Mai 2020"]
    pages = [
        [
            ("-K1", 0.40, 0.44, 0.40, 0.016),
            ("Elektroschema", 0.03, 0.15, 0.93, 0.016),
            _fit("Verteilung Muster", 0.18, 0.93),
            _fit(title, 0.40, 0.93),
            _fit(date, 0.65, 0.915, 0.012),
            _fit("M. Muster", 0.65, 0.945, 0.012),
            ("Blatt", 0.80, 0.86, 0.93, 0.016),
            (str(sheet), 0.88, 0.91, 0.93, 0.016),
        ]
        for sheet, title, date in zip((40, 41, 42), titles, dates, strict=True)
    ]
    path = _ocr_pdf(tmp_path, pages)

    def docling_ohne_ocr(target: Path) -> list[ParsedPage]:
        raw = pdf_raw_text(target)
        return [ParsedPage(page=no, markdown="", raw_text=text) for no, text in raw.items()]

    monkeypatch.setattr(pipeline, "parse_document", docling_ohne_ocr)
    read = pipeline.document_pieces(path, "schematic")
    assert read.titles == dict(enumerate(titles, start=1))
    assert [piece.section for piece in read.pieces] == titles


@pytest.mark.skipif(not QET.exists(), reason="QElectroTech-Testdaten liegen nur lokal (testdata/qelectrotech)")
def test_echte_qet_pdf_bekommt_folio_titel_und_stuecklistenseiten():
    from app.ingestion.docling_parser import pdf_raw_text

    raw = pdf_raw_text(QET)
    titles, parts = page_titles([ParsedPage(page=no, markdown="", raw_text=text) for no, text in sorted(raw.items())])
    assert titles[4] == "Mains Power Supply"
    assert titles[9] == "V1 Gate Control Circuit"
    assert titles[33] == "TB1 Terminal Bord"
    assert 41 in parts and 50 in parts and 9 not in parts
