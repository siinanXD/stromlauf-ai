"""Anschlussnummern am Schaltzeichen ihrem Geraet zuordnen, Kontaktspiegel lesen (Issue #102)."""

from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion.ocr import OcrLine, write_text_layer
from app.ingestion.pdf_layout import pin_labels

W, H = 842, 595  # A4 quer in pt


def _line(text: str, x: float, y: float, size: float = 6) -> OcrLine:
    """Zeile ab (x, y) in pt, Ursprung oben links, so breit wie ihr Text."""
    x0, x1, top = x / W, (x + 0.55 * size * len(text)) / W, y / H
    bottom = (y + size * 1.25) / H
    return OcrLine(text, ((x0, top), (x1, top), (x1, bottom), (x0, bottom)), 0.99)


def _plan(tmp_path: Path, lines: list[OcrLine]) -> Path:
    src, out = tmp_path / "leer.pdf", tmp_path / "plan.pdf"
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(W, H)
    pdf.save(src)
    pdf.close()
    write_text_layer(src, out, {1: lines})
    return out


def _symbol(bmk: str, x: float, y: float, pins: tuple[str, str]) -> list[OcrLine]:
    """Wie make_pdf.coil/contact: Kennzeichen 8 pt, Nummern 6 pt rund 11 pt darueber und darunter."""
    return [_line(bmk, x, y, 8), _line(pins[0], x, y - 11), _line(pins[1], x, y + 13)]


def test_nummern_am_symbol_gehoeren_zum_kennzeichen(tmp_path):
    lines = _symbol("-K1", 300, 300, ("A1", "A2")) + _symbol("-S1", 450, 300, ("13", "14"))
    assert pin_labels(_plan(tmp_path, lines)) == {1: "-K1:A1 -K1:A2\n-S1:13 -S1:14"}


def test_gleich_nah_an_zwei_kennzeichen_wird_nichts_zugeordnet(tmp_path):
    lines = [_line("-K1", 300, 300, 8), _line("-K2", 340, 300, 8), _line("13", 320, 289)]
    assert pin_labels(_plan(tmp_path, lines)) == {}


def test_nie_an_ein_geraet_ohne_art(tmp_path):
    """Am Motor oder an der SPS-Karte sagt eine Nummer nichts; das zweitnaechste Schuetz bekommt sie auch nicht."""
    lines = [
        _line("-M1", 300, 300, 8),
        _line("-K1", 300, 360, 8),
        _line("13", 300, 289),
        _line("-A1.1", 500, 300, 8),
    ]
    lines.append(_line("11", 500, 289))
    assert pin_labels(_plan(tmp_path, lines)) == {}


def test_klemmleiste_ohne_minus_behaelt_ihre_klemmennummern(tmp_path):
    """Schweizer Schreibweise "X1041 3": Die 3 ist eine Klemme der Leiste, nicht der Hauptkontakt des Schuetzes daneben."""
    lines = [_line("X1041", 300, 300, 8), _line("3", 330, 300), _line("-K1", 330, 330, 8)]
    assert pin_labels(_plan(tmp_path, lines)) == {}


def test_weit_weg_ist_keine_anschlussnummer(tmp_path):
    """Spaltennummern im Rahmen oder Mengen in Tabellen stehen nicht am Schaltzeichen."""
    lines = [_line("-K1", 300, 300, 8), _line("4", 300, 240), _line("5", 360, 300)]
    assert pin_labels(_plan(tmp_path, lines)) == {}


def test_kontaktspiegel_unter_der_spule_nennt_den_verweis(tmp_path):
    """Kontaktspiegel: je Zeile die Nummern eines Kontakts und das Blatt.Spalte, wo er gezeichnet ist."""
    lines = _symbol("-K1", 300, 300, ("A1", "A2")) + [
        _line("1", 290, 330), _line("2", 300, 330), _line("/3.4", 312, 330),
        _line("13", 290, 340), _line("14", 302, 340), _line("/5.3", 316, 340),
        _line("21", 290, 350), _line("22", 302, 350), _line("/6.2", 316, 350),
    ]  # fmt: skip
    labels = pin_labels(_plan(tmp_path, lines))[1].splitlines()
    assert labels == [
        "-K1:A1 -K1:A2",
        "-K1:1 -K1:2 /3.4",
        "-K1:13 -K1:14 /5.3",
        "-K1:21 -K1:22 /6.2",
    ]


def test_ohne_kennzeichen_auf_der_seite_nichts(tmp_path):
    assert pin_labels(_plan(tmp_path, [_line("13", 300, 300), _line("A1", 300, 320)])) == {}


def test_pipeline_schreibt_die_anschluesse_in_den_index(tmp_path, monkeypatch):
    """Der Stromlaufplan bekommt einen Block "Anschluesse am Schaltzeichen"; daraus liest der Index -K1:A1."""
    from app.ingestion import pipeline
    from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
    from app.models import TagType

    path = _plan(
        tmp_path, _symbol("-K1", 300, 300, ("A1", "A2")) + _symbol("-S1", 450, 300, ("13", "14"))
    )

    def docling_ohne_ocr(target: Path) -> list[ParsedPage]:
        raw = pdf_raw_text(target)
        return [ParsedPage(page=no, markdown="", raw_text=text) for no, text in raw.items()]

    monkeypatch.setattr(pipeline, "parse_document", docling_ohne_ocr)
    read = pipeline.document_pieces(path, "schematic")
    assert "### Anschlüsse am Schaltzeichen" in read.pieces[0].content
    rows = pipeline.tag_rows(pipeline.split_pieces(read.pieces))
    pins = {row.tag for row in rows if row.tag_type == TagType.DEVICE_PIN}
    assert pins == {"-K1:A1", "-K1:A2", "-S1:13", "-S1:14"}
    # andere Dokumenttypen bekommen den Block nicht
    assert "Anschlüsse" not in pipeline.document_pieces(path, "manual").pieces[0].content
