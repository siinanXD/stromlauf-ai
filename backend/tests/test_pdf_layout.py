import importlib.util
import json
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from app.ingestion.docling_parser import pdf_raw_text
from app.ingestion.ocr import OcrLine, write_text_layer
from app.ingestion.pdf_layout import SheetPage, page_columns, parse_ref, sheet_map, sheet_page

ROOT = Path(__file__).resolve().parents[2]
FB01 = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
SCHRIFTFELD = ROOT / "examples" / "schriftfeld"
GOLD = json.loads((SCHRIFTFELD / "gold.json").read_text(encoding="utf-8"))
VARIANTS = [
    "blatt_schraegstrich.pdf",
    "blatt_von.pdf",
    "bl_punkt.pdf",
    "sheet_of.pdf",
    "getrennte_felder.pdf",
    "eplan_seitenname.pdf",
]
LOCAL = ROOT / "testdata"
QET = [
    "qelectrotech/QET_Beispielprojekt_example_40S.pdf",
    "qelectrotech/QET_Beispielprojekt_industrial_50S.pdf",
]
FESTO = [
    "festo/Festo_MPS_Trennen_Stromlaufplan.pdf",
    "festo/Festo_MPS_Verteilen-Band_Stromlaufplan.pdf",
]


def test_sheet_page_finds_blatt_label():
    assert sheet_page(FB01, 3) == SheetPage(3)


def test_sheet_page_unknown_sheet_is_none():
    assert sheet_page(FB01, 42) == SheetPage(None)


def test_page_columns_reads_header_row():
    columns = page_columns(FB01, 3)
    assert [c.n for c in columns] == list(range(1, 9))
    last = columns[-1]
    assert 0.8 < last.x0 < last.x1 and last.x1 > 0.9
    assert all(c.y0 < 0.1 for c in columns)
    assert all(0.7 < c.y1 < 0.9 for c in columns)
    assert all(a.x1 <= b.x0 + 1e-6 for a, b in zip(columns, columns[1:], strict=False))


def test_page_columns_without_header_is_empty(tmp_path):
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(600, 400)
    target = tmp_path / "leer.pdf"
    pdf.save(target)
    assert page_columns(target, 1) == []


def test_parse_ref_variants():
    assert parse_ref("/3.8") == (3, 8, None)
    assert parse_ref("S. 12") == (None, None, 12)
    assert parse_ref("Kap. 6") == (None, None, None)
    assert parse_ref("S. 3 /3.8") == (3, 8, 3)


def test_sheet_page_is_cached_per_file():
    from app.ingestion.pdf_layout import _sheet_map

    _sheet_map.cache_clear()
    sheet_page(FB01, 3)
    sheet_page(FB01, 5)
    assert _sheet_map.cache_info().hits >= 1


@pytest.mark.parametrize("name", VARIANTS)
def test_schriftfeld_varianten_ordnen_jedes_blatt_seiner_seite_zu(name):
    """Issue #67: Deckblatt und Inhaltsverzeichnis ohne Blatt; Querverweise wie /3.8 und Hinweise wie "von Blatt 3"
    im unteren Viertel der Zeichnung erzeugen keinen Blatt-Eintrag."""
    path = SCHRIFTFELD / name
    sheets = sheet_map(path)
    assert sheets.read == {int(page): sheet for page, sheet in GOLD[name].items()}
    assert sheets.guessed == {}
    assert sheet_page(path, 1) == SheetPage(3)


@pytest.mark.parametrize("name", QET + FESTO)
def test_fremde_plaene_lesen_folio_page_und_seite_aus_dem_schriftfeld(name):
    """QElectroTech ("Folio : 4" ueber dem Folgeblatt "Folio : 5", "Page: 4") und EPLAN bei Festo ("Seite 5",
    darunter "von 10"): jede Seite traegt ihre eigene Nummer."""
    path = LOCAL / name
    if not path.exists():
        pytest.skip("Testdaten liegen nur lokal (testdata/)")
    sheets = sheet_map(path)
    assert sheets.read == {page: page for page in range(1, sheets.page_count + 1)}
    assert sheets.guessed == {}


def test_ohne_blattnummer_gilt_seite_gleich_blatt_als_geraten():
    path = SCHRIFTFELD / "ohne_blattnummer.pdf"
    sheets = sheet_map(path)
    assert sheets.read == {} and sheets.guessed == {page: page for page in range(1, 8)}
    assert sheet_page(path, 2) == SheetPage(2, guessed=True)
    assert sheet_page(path, 9) == SheetPage(None, guessed=True)


def test_luecke_im_schriftfeld_wird_aus_der_seitenfolge_geraten():
    path = SCHRIFTFELD / "luecke.pdf"
    sheets = sheet_map(path)
    assert sheets.read == {3: 1, 4: 2, 6: 4, 7: 5}
    assert sheets.guessed == {5: 3}
    assert sheet_page(path, 3) == SheetPage(5, guessed=True)
    assert sheet_page(path, 4) == SheetPage(6)
    assert sheet_page(path, 9) == SheetPage(None)


def _page_with_lines(tmp_path: Path, lines: list[OcrLine], size=(842, 595)) -> Path:
    src, out = tmp_path / "leer.pdf", tmp_path / "mit_text.pdf"
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(*size)
    pdf.save(src)
    pdf.close()
    write_text_layer(src, out, {1: lines})
    return out


def _horizontal(text: str, x0: float, x1: float, top: float, bottom: float) -> OcrLine:
    return OcrLine(text, ((x0, top), (x1, top), (x1, bottom), (x0, bottom)), 0.99)


@pytest.mark.parametrize(
    "quad",
    [
        # Blatt gegen den Uhrzeigersinn gedreht: Text laeuft an der rechten Kante nach oben
        ((0.86, 0.10), (0.86, 0.04), (0.875, 0.04), (0.875, 0.10)),
        # im Uhrzeigersinn gedreht: Text laeuft an der linken Kante nach unten
        ((0.14, 0.90), (0.14, 0.96), (0.125, 0.96), (0.125, 0.90)),
    ],
    ids=["nach-oben", "nach-unten"],
)
def test_hochkant_gescanntes_blatt_liest_das_schriftfeld_in_leserichtung(tmp_path, quad):
    """Die OCR legt die Zeilen eines hochkant gescannten Blatts gedreht ab (Issue #65); unten in Leserichtung ist
    dann eine Seitenkante."""
    path = _page_with_lines(tmp_path, [OcrLine("Blatt 4 / 7", quad, 0.99)], size=(595, 842))
    assert sheet_map(path).read == {1: 4}


def test_folgeblatt_unter_dem_folio_zaehlt_nicht(tmp_path):
    """QElectroTech zeigt unter "Folio : 4" mit demselben Feldnamen das Folgeblatt."""
    path = _page_with_lines(
        tmp_path,
        [
            _horizontal("Folio : 4", 0.93, 0.98, 0.952, 0.964),
            _horizontal("Folio : 5", 0.93, 0.98, 0.966, 0.978),
        ],
    )
    assert sheet_map(path).read == {1: 4}


def test_querverweise_im_unteren_viertel_sind_kein_blatt(tmp_path):
    path = _page_with_lines(
        tmp_path,
        [
            _horizontal("/3.8", 0.40, 0.44, 0.93, 0.942),
            _horizontal("=ANL+ORT/3.8", 0.80, 0.90, 0.955, 0.967),
        ],
    )
    assert sheet_map(path).read == {}


def test_eplan_seitenname_schlaegt_den_blattzaehler(tmp_path):
    """EPLAN zaehlt "Blatt 3" fortlaufend, Querverweise wie /5.2 nennen aber den Seitennamen =ANL+ORT/5."""
    path = _page_with_lines(
        tmp_path,
        [
            _horizontal("=ANL+ORT/5", 0.80, 0.90, 0.925, 0.937),
            _horizontal("Blatt 3", 0.93, 0.98, 0.955, 0.967),
        ],
    )
    assert sheet_map(path).read == {1: 5}


def test_blattliste_im_unteren_viertel_ist_kein_schriftfeld(tmp_path):
    """Inhaltsverzeichnis mit "Blatt n" in der ersten Spalte, dessen letzte Zeilen ins untere Viertel reichen."""
    path = _page_with_lines(
        tmp_path,
        [
            _horizontal("Blatt 4", 0.10, 0.16, 0.78, 0.79),
            _horizontal("Not-Halt-Kreis", 0.30, 0.45, 0.78, 0.79),
            _horizontal("Blatt 5", 0.10, 0.16, 0.84, 0.85),
            _horizontal("SPS-Eingaenge", 0.30, 0.45, 0.84, 0.85),
        ],
    )
    sheets = sheet_map(path)
    assert sheets.read == {} and sheets.guessed == {1: 1}


def test_blatt_oberhalb_des_unteren_viertels_zaehlt_nicht(tmp_path):
    path = _page_with_lines(tmp_path, [_horizontal("Blatt 9", 0.10, 0.16, 0.30, 0.31)])
    assert sheet_map(path).read == {}


def _pdf_with_pages(tmp_path: Path, pages: list[list[OcrLine]]) -> Path:
    src, out = tmp_path / "leer.pdf", tmp_path / "mit_text.pdf"
    pdf = pdfium.PdfDocument.new()
    for _ in pages:
        pdf.new_page(842, 595)
    pdf.save(src)
    pdf.close()
    write_text_layer(
        src, out, {number: lines for number, lines in enumerate(pages, start=1) if lines}
    )
    return out


def test_einzelne_zeile_des_inhaltsverzeichnisses_verdraengt_das_blatt_nicht(tmp_path):
    """Nur die letzte Zeile "Blatt 3" reicht ins untere Viertel; Blatt 3 ist trotzdem Seite 4, nicht Seite 1."""
    title = lambda sheet: [_horizontal(f"Blatt {sheet} / 3", 0.90, 0.98, 0.94, 0.952)]  # noqa: E731
    path = _pdf_with_pages(
        tmp_path, [[_horizontal("Blatt 3", 0.10, 0.16, 0.80, 0.81)], title(1), title(2), title(3)]
    )
    sheets = sheet_map(path)
    assert sheets.read == {2: 1, 3: 2, 4: 3} and sheets.gaps == ()


def test_generator_erzeugt_die_eingecheckten_fixtures(tmp_path):
    """make_titleblocks.py und examples/schriftfeld passen zusammen; verglichen wird der Text, nicht die Bytes, weil
    andere reportlab-Versionen anders komprimieren."""
    pytest.importorskip("reportlab")
    path = ROOT / "scripts" / "example_docs" / "make_titleblocks.py"
    spec = importlib.util.spec_from_file_location("make_titleblocks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.gold() == GOLD
    assert sorted(module.VARIANTS) == sorted(p.name for p in SCHRIFTFELD.glob("*.pdf"))
    for name, field in module.VARIANTS.items():
        module.build(tmp_path / name, field)
        assert pdf_raw_text(tmp_path / name) == pdf_raw_text(SCHRIFTFELD / name), name
