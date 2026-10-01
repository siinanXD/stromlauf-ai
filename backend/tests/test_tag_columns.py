"""Spalte je Geraetekennzeichen einer Planseite (app/ingestion/tag_columns.py, Spur B3).

Die Seiten entstehen per unsichtbarer Textebene (ocr.write_text_layer) wie in test_column_text.py.
"""

from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion import tag_columns as module
from app.ingestion.ocr import OcrLine, write_text_layer
from app.ingestion.tag_columns import tag_columns


def _line(text: str, center: float, top: float, width: float = 0.035) -> OcrLine:
    x0, x1, bottom = center - width / 2, center + width / 2, top + 0.014
    return OcrLine(text, ((x0, top), (x1, top), (x1, bottom), (x0, bottom)), 0.99)


def _column(n: int) -> float:
    return 0.1 * n  # Spalte n hat ihre Mitte bei 0.1 * n (Kopfzeile 1 bis 8)


def _pdf(tmp_path: Path, pages: list[list[OcrLine]]) -> Path:
    src, out = tmp_path / "leer.pdf", tmp_path / "plan.pdf"
    pdf = pdfium.PdfDocument.new()
    for _ in pages:
        pdf.new_page(842, 595)
    pdf.save(src)
    pdf.close()
    write_text_layer(src, out, {number: lines for number, lines in enumerate(pages, start=1)})
    return out


def _plan_page() -> list[OcrLine]:
    header = [_line(str(n), _column(n), 0.05, 0.01) for n in range(1, 9)]
    return header + [
        _line("-K1", _column(3), 0.30),  # Spule
        _line("-K1:A1", _column(3), 0.40, 0.05),  # Anschluss an derselben Spule
        _line("-K1", _column(6), 0.30),  # Kontakt in einer anderen Spalte
        _line("-S2", _column(6), 0.55),
        _line("=FB1+ST1-Q4", _column(1), 0.60, 0.09),  # mit Anlage und Ort
        _line("-X1:5", _column(5), 0.50, 0.04),  # Klemme, kein Geraet
        _line("Anlage -M9", _column(2), 0.92, 0.10),  # Schriftfeld
        _line("Blatt 3 / 7", _column(7), 0.92, 0.08),
    ]


def test_spalte_je_kennzeichen_aus_kopfzeile_und_wortposition(tmp_path):
    plan = _pdf(tmp_path, [_plan_page()])
    assert tag_columns(plan, 1) == {"-K1": 3, "-S2": 6, "-Q4": 1, "=FB1+ST1-Q4": 1}


def test_gleichstand_nimmt_die_linke_spalte(tmp_path):
    header = [_line(str(n), _column(n), 0.05, 0.01) for n in range(1, 9)]
    plan = _pdf(tmp_path, [header + [_line("-K7", _column(5), 0.3), _line("-K7", _column(2), 0.6)]])
    assert tag_columns(plan, 1) == {"-K7": 2}


def test_ohne_spaltenraster_und_ausserhalb_der_seiten_leer(tmp_path):
    plan = _pdf(tmp_path, [[_line("-K1", 0.3, 0.3), _line("-S2", 0.6, 0.3)]])
    assert tag_columns(plan, 1) == {}
    assert tag_columns(plan, 2) == {}


def test_je_datei_und_seite_einmal_gerechnet(tmp_path, monkeypatch):
    plan = _pdf(tmp_path, [_plan_page()])
    calls = []
    original = module.page_columns
    monkeypatch.setattr(
        module, "page_columns", lambda path, page: calls.append(page) or original(path, page)
    )
    module._tag_columns.cache_clear()
    first = tag_columns(plan, 1)
    first["-K1"] = 99  # das Ergebnis ist eine Kopie, der Cache bleibt unberuehrt
    assert tag_columns(plan, 1)["-K1"] == 3
    assert calls == [1]
