from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion.pdf_layout import page_columns, parse_ref, sheet_page

FB01 = Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"


def test_sheet_page_finds_blatt_label():
    assert sheet_page(FB01, 3) == 3


def test_sheet_page_unknown_sheet_is_none():
    assert sheet_page(FB01, 42) is None


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
