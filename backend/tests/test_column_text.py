"""Text je Spalte (Issue #90): Laufen die Signalwege eines Stromlaufplans als Spalten von oben nach unten (Taster,
Klemme, SPS-Eingang untereinander), bekommt der Chat die Beschriftungen einer Spalte zusammen. Seiten, deren Kanaele
als Zeilen laufen, behalten den Rohtext in pdfium-Reihenfolge, denn der haelt dort die Zeile zusammen.

Die Seiten entstehen im Test per unsichtbarer Textebene (ocr.write_text_layer), Docling laeuft nicht.
"""

from pathlib import Path

import pypdfium2 as pdfium
import pytest

from app.ingestion import pipeline
from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
from app.ingestion.ocr import OcrLine, write_text_layer
from app.ingestion.pdf_layout import column_texts, page_columns

CENTERS = [0.1 + 0.1 * i for i in range(8)]  # Spalten 1 bis 8


def _line(text: str, center: float, top: float, width: float, height: float = 0.014) -> OcrLine:
    x0, x1, bottom = center - width / 2, center + width / 2, top + height
    return OcrLine(text, ((x0, top), (x1, top), (x1, bottom), (x0, bottom)), 0.99)


def _header(first: int = 1, count: int = 8, step: float = 0.1, start: float = 0.1) -> list[OcrLine]:
    return [_line(str(first + i), start + step * i, 0.05, 0.01) for i in range(count)]


def _pdf(tmp_path: Path, pages: list[list[OcrLine]], name: str = "plan.pdf") -> Path:
    src, out = tmp_path / "leer.pdf", tmp_path / name
    pdf = pdfium.PdfDocument.new()
    for _ in pages:
        pdf.new_page(842, 595)
    pdf.save(src)
    pdf.close()
    write_text_layer(src, out, {number: lines for number, lines in enumerate(pages, start=1)})
    return out


def _signal_columns() -> list[OcrLine]:
    """Acht Signalwege nebeneinander wie in einem Schweizer Elektroschema: Taster, Klemme, Eingang, Beschreibung."""
    lines = _header()
    for i, center in enumerate(CENTERS, start=1):
        lines += [
            _line(f"-S{i}", center, 0.25, 0.035),
            _line(f"-X2:{i}", center, 0.45, 0.04),
            _line(f"E0.{i - 1}", center, 0.65, 0.035),
            _line(f"Taster {i}", center, 0.70, 0.05),
        ]
    lines.append(_line("Hinweis: alle Taster schliessen", 0.21, 0.78, 0.30))
    lines += [_line("Anlage Testanlage", 0.15, 0.92, 0.20), _line("Blatt 42", 0.90, 0.92, 0.08)]
    return lines


def _signal_rows() -> list[OcrLine]:
    """Kanaele als Zeilen wie in FB-01: Adresse, Klemme und Geber stehen in einer Zeile nebeneinander."""
    lines = _header()
    for row in range(4):
        top = 0.2 + 0.1 * row
        lines += [
            _line(f"E0.{row}", CENTERS[1], top, 0.035),
            _line(f"-X3:{row + 1}", CENTERS[2], top, 0.04),
            _line(f"von -S{row + 1}", CENTERS[5], top, 0.06),
        ]
    lines.append(_line("Blatt 7", 0.90, 0.92, 0.07))
    return lines


def _blocks(text: str) -> dict[str, list[str]]:
    blocks = {}
    for block in text.strip().split("\n\n"):
        head, *lines = block.split("\n")
        assert head.endswith(":"), head
        blocks[head[:-1]] = lines
    return blocks


def test_beschriftungen_einer_spalte_stehen_zusammen_und_in_der_reihenfolge_des_plans(tmp_path):
    texts = column_texts(_pdf(tmp_path, [_signal_columns()]))
    blocks = _blocks(texts[1])
    for i in range(1, 9):
        expected = [f"-S{i}", f"-X2:{i}", f"E0.{i - 1}", f"Taster {i}"]
        assert [line for line in blocks[f"Spalte {i}"] if line in expected] == expected, i
    # der Nachbar steht nicht im selben Block: Klemme und Eingang gehoeren zum Taster darueber
    assert "E0.1" not in blocks["Spalte 1"] and "-X2:1" not in blocks["Spalte 2"]


def test_kennzeichen_links_vom_strompfad_gehoert_zu_seinem_strompfad(tmp_path):
    """Wie im Schweizer Elektroschema: Der Strompfad liegt links der Spaltenmitte, das Kennzeichen steht links daneben
    und ragt mit seiner Mitte in die Nachbarspalte. Massgeblich ist der Strompfad, nicht die Grenze der Kopfzeile."""
    lines = _header()
    for i, center in enumerate(CENTERS, start=1):
        path = center - 0.035
        lines += [
            _line(f"-S{i}", path - 0.025, 0.25, 0.04),  # endet kurz vor dem Strompfad
            _line(f"X2 {i}", path, 0.45, 0.04),
            _line(f"E0.{i - 1}", path, 0.65, 0.035),
        ]
    blocks = _blocks(column_texts(_pdf(tmp_path, [lines]))[1])
    for i in range(1, 9):
        expected = [f"-S{i}", f"X2 {i}", f"E0.{i - 1}"]
        assert [line for line in blocks[f"Spalte {i}"] if line in expected] == expected, i


def test_beschriftungen_fern_jedes_strompfads_bleiben_in_ihrer_spalte(tmp_path):
    """Wie FB-01 Blatt 4: rechts drei Eingaenge nebeneinander, links Sicherheitskreise ohne SPS-Adresse. Was weit weg
    von jedem Strompfad steht, bleibt in der Spalte der Kopfzeile, statt beim naechsten Strompfad zu landen."""
    lines = _header()
    lines += [_line("-K3", CENTERS[0], 0.30, 0.03), _line("-H1", CENTERS[1], 0.40, 0.03)]
    for i in (6, 7, 8):
        address = _line(f"E0.{i - 1}", CENTERS[i - 1], 0.65, 0.035)
        lines += [_line(f"-S{i}", CENTERS[i - 1], 0.25, 0.03), address]
    blocks = _blocks(column_texts(_pdf(tmp_path, [lines]))[1])
    assert blocks["Spalte 1"] == ["-K3"] and blocks["Spalte 2"] == ["-H1"]
    assert blocks["Spalte 6"] == ["-S6", "E0.5"]


def test_hinweise_ueber_mehrere_spalten_und_das_schriftfeld_stehen_fuer_sich(tmp_path):
    """Ein Satz ueber mehrere Spalten bleibt ganz und gehoert keinem Strompfad; das Schriftfeld ist ein eigener Block."""
    blocks = _blocks(column_texts(_pdf(tmp_path, [_signal_columns()]))[1])
    assert blocks["Hinweise"] == ["Hinweis: alle Taster schliessen"]
    assert blocks["Schriftfeld"] == ["Anlage Testanlage", "Blatt 42"]
    lines = [line for block in blocks.values() for line in block]
    # die Spaltennummern selbst sind keine Beschriftung
    assert not {str(n) for n in range(1, 9)} & set(lines)


def test_kanaele_als_zeilen_behalten_den_rohtext(tmp_path):
    """FB-01, UR-01, PM1-AR zeichnen die SPS-Kanaele als Zeilen; je Spalte sortiert risse das die Zeile auseinander."""
    assert column_texts(_pdf(tmp_path, [_signal_rows()])) == {}


def test_nur_seiten_mit_signalspalten_werden_neu_geordnet(tmp_path):
    path = _pdf(tmp_path, [_signal_rows(), _signal_columns(), [_line("Deckblatt", 0.5, 0.3, 0.2)]])
    assert set(column_texts(path)) == {2}


def test_spalten_ab_null_wie_im_schweizer_elektroschema(tmp_path):
    """Nummerierung 0 bis 9: Querverweise wie /40.0 zeigen dann auf Spalte 0."""
    path = _pdf(tmp_path, [_header(first=0, count=10, step=0.09, start=0.06)])
    assert [column.n for column in page_columns(path, 1)] == list(range(10))


def _docling_ohne_ocr(path: Path) -> list[ParsedPage]:
    raw = pdf_raw_text(path)
    return [ParsedPage(page=page, markdown="", raw_text=text) for page, text in raw.items()]


@pytest.fixture
def ohne_docling(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_document", _docling_ohne_ocr)


def test_stromlaufplan_bekommt_die_spalten_andere_dokumente_den_rohtext(tmp_path, ohne_docling):
    path = _pdf(tmp_path, [_signal_columns()])
    (schematic,) = pipeline.document_pieces(path, "schematic").pieces
    assert "### Beschriftungen je Spalte" in schematic.content and "Spalte 1:" in schematic.content
    (manual,) = pipeline.document_pieces(path, "manual").pieces
    assert "### Beschriftungen (Rohtext)" in manual.content and "Spalte 1:" not in manual.content


def test_die_kennzeichen_bleiben_dieselben(tmp_path, ohne_docling):
    """Nur die Reihenfolge aendert sich: der Kennzeichen-Index bekommt dieselben Funde wie aus dem Rohtext."""
    path = _pdf(tmp_path, [_signal_columns()])

    def tags(doc_type: str) -> set[tuple[str, str]]:
        pieces = pipeline.document_pieces(path, doc_type).pieces
        return {(row.tag, str(row.tag_type)) for row in pipeline.tag_rows(pieces)}

    assert tags("schematic") == tags("manual")
    assert ("-X2:8", "terminal") in tags("schematic")
