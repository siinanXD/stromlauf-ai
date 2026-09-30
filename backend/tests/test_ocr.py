"""OCR-Kern (Issue #65): RapidOCR lokal und unsichtbare Textebene, sodass alle Leser der Textebene Scans lesen.

Die Textebenen-Tests brauchen keine Texterkennung: Sie schreiben die Textrechtecke des FB-01-Text-PDFs als
"OCR-Zeilen" auf die Bildseiten des Scans und lesen mit den vorhandenen Lesern zurueck. Nur die letzten Tests
rufen RapidOCR selbst auf (mitgelieferte Modelle, onnxruntime, kein Netz).
"""

import json
import math
import socket
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.ingestion import ocr
from app.ingestion.docling_parser import pdf_raw_text
from app.ingestion.pdf_layout import page_columns, sheet_map
from app.ingestion.tags import extract_tags

ROOT = Path(__file__).resolve().parents[2]
TEXT = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
SCAN = ROOT / "examples" / "scan" / "01_Stromlaufplan_FB-01_scan.pdf"
PARTIAL = ROOT / "examples" / "scan" / "01_Stromlaufplan_FB-01_teilscan.pdf"
SIDEWAYS = ROOT / "examples" / "scan" / "01_Stromlaufplan_FB-01_quer.pdf"
GOLD = json.loads((ROOT / "eval" / "ingest_gold" / "fb01.json").read_text(encoding="utf-8"))[
    "seiten"
]


def _lines_from_text_layer(path: Path, page: int) -> list[ocr.OcrLine]:
    """Textrechtecke einer Text-PDF-Seite als OCR-Zeilen (relativ, Ursprung oben links)."""
    pdf = pdfium.PdfDocument(str(path))
    try:
        width, height = pdf[page - 1].get_size()
        textpage = pdf[page - 1].get_textpage()
        lines = []
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            text = textpage.get_text_bounded(left, bottom, right, top).strip()
            if text:
                quad = (
                    (left / width, 1 - top / height),
                    (right / width, 1 - top / height),
                    (right / width, 1 - bottom / height),
                    (left / width, 1 - bottom / height),
                )
                lines.append(ocr.OcrLine(text, quad, 1.0))
        return lines
    finally:
        pdf.close()


def _tags(text: str) -> set[str]:
    return {tag.tag for tag in extract_tags(text)}


@pytest.fixture(scope="module")
def blatt_3_mit_textebene(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("ocr") / "scan_mit_textebene.pdf"
    ocr.write_text_layer(SCAN, out, {3: _lines_from_text_layer(TEXT, 3)})
    return out


def test_textebene_macht_blatt_und_spalten_des_scans_lesbar(blatt_3_mit_textebene):
    sheets = sheet_map(blatt_3_mit_textebene)
    assert sheets.read == {3: 3} and sheets.page_count == 7
    # die Bildseiten ohne Textebene davor und bis zur Blattanzahl "/ 7" danach sind nur angenommen (Issue #67)
    assert sheets.guessed == {1: 1, 2: 2, 4: 4, 5: 5, 6: 6, 7: 7}
    scanned = page_columns(blatt_3_mit_textebene, 3)
    original = page_columns(TEXT, 3)
    assert len(scanned) == len(original) == 8
    assert (
        max(abs(a.x0 - b.x0) + abs(a.x1 - b.x1) for a, b in zip(scanned, original, strict=True))
        <= 0.01
    )


def test_textebene_haelt_kennzeichen_mit_minus_zusammen(blatt_3_mit_textebene):
    """Regression aus dem Spike: ein Textobjekt je Zeile, sonst landet das Minus von -Q1 auf eigener Zeile."""
    text = pdf_raw_text(blatt_3_mit_textebene)[3]
    assert {"-Q1", "-K1", "-K2", "-M1", "-X4:PE"} <= _tags(text)
    assert not pdf_raw_text(blatt_3_mit_textebene)[2].strip()  # andere Bildseiten bleiben ohne Text


def test_textebene_schreibt_umlaute_und_gedrehte_zeilen(tmp_path):
    horizontal = ocr.OcrLine(
        "Förderband Schütz -K1", ((0.1, 0.1), (0.5, 0.1), (0.5, 0.14), (0.1, 0.14)), 0.9
    )
    # hochkant, von unten nach oben zu lesen: oben links der Leserichtung liegt unten links auf der Seite
    vertical = ocr.OcrLine("-X2:5 Klemme", ((0.8, 0.9), (0.8, 0.5), (0.84, 0.5), (0.84, 0.9)), 0.9)
    out = tmp_path / "zeilen.pdf"
    ocr.write_text_layer(SCAN, out, {1: [horizontal, vertical]})
    text = pdf_raw_text(out)[1]
    assert "Förderband Schütz -K1" in text and "-X2:5 Klemme" in text
    pdf = pdfium.PdfDocument(str(out))
    try:
        textpage = pdf[0].get_textpage()
        start = text.index("-X2:5")
        boxes = [textpage.get_charbox(start + offset) for offset in range(5)]
    finally:
        pdf.close()
    lefts = [box[0] for box in boxes]
    bottoms = [box[1] for box in boxes]
    assert max(lefts) - min(lefts) < 12 and bottoms == sorted(bottoms)  # Zeichen laufen nach oben


def test_nebeneinander_liegende_zeilen_verschmelzen_nicht(tmp_path):
    """Die Boxen der Detektion sind breiter als die Schrift; ohne Trennung liest pdfium "6E0.5" und die
    Grammatik verwirft E0.5 (Blatt 5 des Voll-Scans, gemessen 2026-09-29)."""
    number = ocr.OcrLine("6", ((0.100, 0.30), (0.125, 0.30), (0.125, 0.33), (0.100, 0.33)), 0.99)
    address = ocr.OcrLine(
        "E0.5", ((0.124, 0.30), (0.175, 0.30), (0.175, 0.33), (0.124, 0.33)), 0.99
    )
    out = tmp_path / "nachbarn.pdf"
    ocr.write_text_layer(SCAN, out, {5: [number, address]})
    assert "E0.5" in _tags(pdf_raw_text(out)[5])


def test_normalisierung_trennt_kennzeichen_und_vereinheitlicht_striche():
    assert ocr.normalize("O-X2:3 +24 V") == "O -X2:3 +24 V"
    assert ocr.normalize("von-S2") == "von -S2"
    assert ocr.normalize("auf-X3:5 bzw.-X3:6.") == "auf -X3:5 bzw. -X3:6."
    assert ocr.normalize("–K1 und —K2 und −K3 und 一K4") == "-K1 und -K2 und -K3 und -K4"
    assert ocr.normalize("－X1：5") == "-X1:5"  # Vollbreite wie aus dem chinesischen Modell
    for unchanged in (
        "(-Q1)",
        "FB-01",
        "Not-Halt",
        "3-polig",
        "E0.0 bis E0.5",
        "Zeichnungs-Nr. FB-01-E-001",
    ):
        assert ocr.normalize(unchanged) == unchanged


def test_seiten_ohne_text_und_native_aufloesung():
    assert ocr.pages_without_text(SCAN) == list(range(1, 8))
    assert ocr.pages_without_text(PARTIAL) == [3]
    assert ocr.pages_without_text(TEXT) == []
    pdf = pdfium.PdfDocument(str(SCAN))
    try:
        assert ocr.page_dpi(pdf[0]) == 200  # eingebettetes Bild mit 200 dpi
    finally:
        pdf.close()
    text = pdfium.PdfDocument(str(TEXT))
    try:
        assert ocr.page_dpi(text[0]) == ocr.DEFAULT_DPI  # kein Bild: Standard
    finally:
        text.close()


def test_schraeglage_aus_langen_zeilen():
    def box(angle: float, width: float, height: float = 30) -> np.ndarray:
        radians = math.radians(angle)
        direction = np.array([math.cos(radians), math.sin(radians)])
        down = np.array([-math.sin(radians), math.cos(radians)])
        start = np.array([100.0, 100.0])
        return np.array(
            [
                start,
                start + width * direction,
                start + width * direction + height * down,
                start + height * down,
            ]
        )

    boxes = [box(-0.5, 900), box(-0.6, 1200), box(-0.4, 700), box(10, 40)]  # kurze Box zaehlt nicht
    assert ocr.skew_angle(boxes) == pytest.approx(-0.5, abs=0.05)
    assert ocr.skew_angle([box(3, 40)]) == 0.0


def test_punkte_aus_gedrehtem_bild_zurueckrechnen():
    original = Image.new("L", (400, 200), 255)
    for angle in (90, -90, 0.5):
        rotated = original.rotate(angle, expand=True)
        point = np.array([[100.0, 50.0]])
        # Punkt wie PIL drehen: um die Mitte, gegen den Uhrzeigersinn, y nach unten
        radians = math.radians(angle)
        centered = point - np.array([200.0, 100.0])
        turned = np.array(
            [
                [
                    centered[0, 0] * math.cos(radians) + centered[0, 1] * math.sin(radians),
                    -centered[0, 0] * math.sin(radians) + centered[0, 1] * math.cos(radians),
                ]
            ]
        ) + np.array([rotated.width / 2, rotated.height / 2])
        back = ocr.to_original(turned, angle, rotated.size, original.size)
        assert back == pytest.approx(point, abs=1e-6)


def test_schnitte_liegen_in_wortluecken():
    strip = np.full((30, 600), 255, dtype=np.uint8)
    for left, right in (
        (10, 180),
        (200, 330),
        (360, 590),
    ):  # drei Woerter, Luecken 180-200 und 330-360
        strip[8:22, left:right] = 0
    cuts = ocr.split_points(strip, 2)
    assert cuts[0] == 0 and cuts[-1] == 600 and len(cuts) == 3
    assert (
        330 <= cuts[1] <= 360
    )  # Mitte der Zeile liegt bei 300, die naechste Wortluecke bei 330-360


def test_erkennung_laeuft_ohne_netz(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError("Netz gesperrt")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    ocr.reset_engine()
    image = Image.new("L", (600, 120), 255)
    pdf = pdfium.PdfDocument(str(SCAN))
    try:
        page = pdf[2].render(scale=200 / 72).to_pil().convert("L")
    finally:
        pdf.close()
    image = page.crop((1150, 1380, 2300, 1520))  # Schriftfeld rechts unten mit "Blatt 3 / 7"
    lines = ocr.recognize(image)
    assert any("Blatt 3" in line.text for line in lines)


def test_lange_zeilen_von_blatt_1_werden_vollstaendig_gelesen():
    """Auf der ganzen Seite liest das Modell Zeilen ueber etwa 110 Zeichen abgeschnitten oder verstuemmelt
    (gemessen 2026-09-29); geteilt an Wortluecken kommen sie vollstaendig."""
    pdf = pdfium.PdfDocument(str(SCAN))
    try:
        page = pdf[0].render(scale=200 / 72).to_pil().convert("L")
    finally:
        pdf.close()
    lines, rotation, skew = ocr.read_page(page)
    assert rotation == 0 and skew == pytest.approx(-0.5, abs=0.15)
    text = " ".join(line.text for line in lines)
    assert {"E0.0", "E0.5", "A4.0", "A4.3", "E0.3", "-F3", "-P1"} <= _tags(text)


def test_durchsuchbares_pdf_aus_dem_teilscan(tmp_path):
    out = tmp_path / "teilscan_ocr.pdf"
    report = ocr.searchable_pdf(PARTIAL, out)
    assert [page.page for page in report.pages] == [3] and report.pages[0].dpi == 200
    assert report.confidence is not None and report.confidence > 0.8
    texts = pdf_raw_text(out)
    gold = {tag for kind in ("device", "terminal") for tag in GOLD["3"].get(kind, [])}
    assert len(gold & _tags(texts[3])) / len(gold) >= 0.85
    assert texts[1] == pdf_raw_text(PARTIAL)[1]  # Textseiten bleiben unveraendert
    assert ocr.pages_without_text(out) == []


def test_spalten_des_schief_gescannten_blatts_werden_gefunden(tmp_path):
    """Echte OCR: Der Scan ist 0,5 Grad schief, die Spaltennummern fallen ueber die Blattbreite um etwa 0,012
    Seitenhoehen ab. Die Spaltenerkennung muss sie trotzdem als eine Kopfzeile lesen."""
    out = tmp_path / "blatt3_ocr.pdf"
    ocr.searchable_pdf(SCAN, out, pages=[3])
    scanned, original = page_columns(out, 3), page_columns(TEXT, 3)
    assert len(scanned) == len(original) == 8
    assert (
        max(abs(a.x0 - b.x0) + abs(a.x1 - b.x1) for a, b in zip(scanned, original, strict=True))
        <= 0.01
    )


def test_hochkant_gescanntes_blatt_wird_gedreht_erkannt(tmp_path):
    out = tmp_path / "quer_ocr.pdf"
    report = ocr.searchable_pdf(SIDEWAYS, out)
    assert [page.page for page in report.pages] == [4] and report.pages[0].rotation in (90, 270)
    gold = {(tag, kind) for kind, tags in GOLD["4"].items() if kind != "cross_ref" for tag in tags}
    found = {(tag.tag, str(tag.tag_type)) for tag in extract_tags(pdf_raw_text(out)[4])}
    assert len(gold & found) / len(gold) >= 0.8
