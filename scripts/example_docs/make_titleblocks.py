"""Kleine Plan-PDFs mit verschiedenen Schriftfeldern fuer die Blatt-Map (Issue #67).

Aufruf:  python scripts/example_docs/make_titleblocks.py [ZIELORDNER]      (Standard: examples/schriftfeld)

Jede Datei hat vorne ein Deckblatt und ein Inhaltsverzeichnis ohne Blattnummer, danach die Blaetter 1 bis 5 mit
Spaltenraster, Betriebsmitteln und Querverweisen (/4.7, auch im unteren Viertel direkt ueber dem Schriftfeld).
Blatt 1 liegt also auf Seite 3. Je Datei ein anderes Schriftfeld:

- blatt_schraegstrich.pdf  "Blatt 3 / 5"
- blatt_von.pdf            "Blatt 3 von 5"
- bl_punkt.pdf             "Bl. 3"
- sheet_of.pdf             "Sheet 3 of 5"
- getrennte_felder.pdf     Feldname "Blatt" in einer eigenen Zeile, darunter "3", daneben "von 5"
- eplan_seitenname.pdf     EPLAN-Seitenname "=ANL+ORT/3", Querverweise auch als "=ANL+ORT/4.7"
- luecke.pdf               wie "Blatt 3 / 5", aber im Schriftfeld von Blatt 3 fehlt die Nummer
- ohne_blattnummer.pdf     Schriftfeld ganz ohne Blattnummer

Das Gold (Seite -> Blatt, wie gezeichnet) steht in gold.json. reportlab schreibt mit invariant=1 gleiche Bytes je
Lauf. Frei erfundene Anlage, frei verwendbar (MIT-Lizenz des Repos).
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = ROOT / "examples" / "schriftfeld"

W, H = landscape(A4)
MARGIN = 28
FRAME_BOTTOM = MARGIN + 60  # Oberkante des Schriftfelds
COLS = 8
COL_W = (W - 2 * MARGIN) / COLS
FRONT_PAGES = 2  # Deckblatt und Inhaltsverzeichnis
TITLES = [
    "Einspeisung 400 V",
    "Steuerspannung 24 V DC",
    "Motorsteuerung Band",
    "Not-Halt-Kreis",
    "SPS-Eingaenge",
]
TOTAL = len(TITLES)
# Je Blatt: Betriebsmittel (Spalte, BMK, Text) und Querverweise (Spalte, Hoehe in pt, Verweis). Die Hoehe 100 liegt
# im unteren Viertel der Seite direkt ueber dem Schriftfeld, dort, wo die Blatt-Map sucht.
DEVICES = [
    [(2, "-Q1", "Hauptschalter"), (5, "-F1", "Motorschutz"), (7, "-T1", "Netzteil")],
    [(2, "-F2", "Sicherung 24 V"), (4, "-G1", "Netzteil 24 V"), (7, "-X1", "Klemmleiste")],
    [(2, "-K1", "Schuetz Band"), (4, "-M1", "Bandmotor"), (6, "-S1", "Taster Start")],
    [(2, "-S0", "Not-Halt"), (4, "-K3", "Sicherheitsrelais"), (6, "-H1", "Leuchte")],
    [(2, "-A1", "SPS-Eingang E0.0"), (4, "-B1", "Endschalter"), (6, "-B2", "Lichtschranke")],
]
XREFS = [
    [(3, 300, "/2.3"), (6, 100, "/3.8")],
    [(3, 300, "/1.5"), (5, 100, "/4.7")],
    [(3, 300, "/2.6"), (6, 100, "/5.2")],
    [(3, 300, "/3.1"), (5, 100, "/1.2")],
    [(3, 300, "/4.4"), (6, 100, "/3.3")],
]
# Hinweistext im unteren Viertel wie in echten Plaenen; darf die Blattnummer des Schriftfelds nicht verdraengen
NOTES = {2: "Fortsetzung auf Blatt 3", 4: "von Blatt 3"}


def col_x(col: float) -> float:
    return MARGIN + (col - 0.5) * COL_W


def _frame(c: canvas.Canvas) -> None:
    c.setLineWidth(0.8)
    c.rect(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN)
    c.line(MARGIN, FRAME_BOTTOM, W - MARGIN, FRAME_BOTTOM)
    c.line(W - MARGIN - 170, MARGIN, W - MARGIN - 170, FRAME_BOTTOM)


def _title_block(c: canvas.Canvas, title: str) -> None:
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN + 6, FRAME_BOTTOM - 16, "Muster-Band MB-02  =ANL+ORT")
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN + 6, FRAME_BOTTOM - 30, title)
    c.drawString(MARGIN + 6, FRAME_BOTTOM - 44, "Beispiel fuer Stromlauf AI, frei erfunden")
    c.drawString(W / 2 - 40, FRAME_BOTTOM - 16, "Stand: 2026-09  Rev. A")


def _right(c: canvas.Canvas, text: str, size: float = 10) -> None:
    c.setFont("Helvetica", size)
    c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 16, text)


def field_slash(c: canvas.Canvas, sheet: int) -> None:
    _right(c, f"Blatt {sheet} / {TOTAL}")


def field_von(c: canvas.Canvas, sheet: int) -> None:
    _right(c, f"Blatt {sheet} von {TOTAL}")


def field_bl(c: canvas.Canvas, sheet: int) -> None:
    _right(c, f"Bl. {sheet}")


def field_sheet(c: canvas.Canvas, sheet: int) -> None:
    _right(c, f"Sheet {sheet} of {TOTAL}")


def field_separate(c: canvas.Canvas, sheet: int) -> None:
    """Feld "Blatt" wie in vielen Normschriftfeldern: Name klein oben, Nummer gross darunter, Anzahl daneben."""
    x0 = W - MARGIN - 120
    c.setLineWidth(0.5)
    c.line(x0, MARGIN, x0, FRAME_BOTTOM)
    c.setFont("Helvetica", 6)
    c.drawString(x0 + 5, FRAME_BOTTOM - 9, "Blatt")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0 + 8, FRAME_BOTTOM - 32, str(sheet))
    c.setFont("Helvetica", 7)
    c.drawString(x0 + 30, FRAME_BOTTOM - 32, f"von {TOTAL}")


def field_eplan(c: canvas.Canvas, sheet: int) -> None:
    _right(c, f"=ANL+ORT/{sheet}")


def field_gap(c: canvas.Canvas, sheet: int) -> None:
    if sheet != 3:
        field_slash(c, sheet)


def field_none(c: canvas.Canvas, sheet: int) -> None:
    _right(c, "Zeichnungs-Nr. MB-02-E-001", 8)


VARIANTS: dict[str, Callable[[canvas.Canvas, int], None]] = {
    "blatt_schraegstrich.pdf": field_slash,
    "blatt_von.pdf": field_von,
    "bl_punkt.pdf": field_bl,
    "sheet_of.pdf": field_sheet,
    "getrennte_felder.pdf": field_separate,
    "eplan_seitenname.pdf": field_eplan,
    "luecke.pdf": field_gap,
    "ohne_blattnummer.pdf": field_none,
}


def cover(c: canvas.Canvas) -> None:
    _frame(c)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(W / 2, H - 150, "Stromlaufplan")
    c.setFont("Helvetica", 12)
    for index, line in enumerate(
        ["Muster-Band MB-02", "Anlage =ANL+ORT", "Kunde: Beispiel GmbH", "Stand: 2026-09  Rev. A"]
    ):
        c.drawCentredString(W / 2, H - 200 - 20 * index, line)
    _title_block(c, "Deckblatt")


def contents(c: canvas.Canvas) -> None:
    """Inhaltsverzeichnis als Tabelle; die letzten Zeilen reichen ins untere Viertel der Seite."""
    _frame(c)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN + 40, H - 80, "Inhaltsverzeichnis")
    c.setFont("Helvetica-Bold", 9)
    for x, head in ((MARGIN + 40, "Blatt"), (MARGIN + 110, "Titel"), (MARGIN + 520, "Stand")):
        c.drawString(x, 290, head)
    c.setFont("Helvetica", 9)
    for index, title in enumerate(TITLES):
        y = 250 - 37 * index
        c.drawString(MARGIN + 40, y, str(index + 1))
        c.drawString(MARGIN + 110, y, title)
        c.drawString(MARGIN + 520, y, "2026-09")
    _title_block(c, "Inhaltsverzeichnis")


def draw_sheet(c: canvas.Canvas, sheet: int, field: Callable[[canvas.Canvas, int], None]) -> None:
    _frame(c)
    c.setFont("Helvetica", 8)
    top = H - MARGIN
    for i in range(COLS):
        x = MARGIN + i * COL_W
        c.line(x, top, x, top - 12)
        c.drawCentredString(x + COL_W / 2, top - 9, str(i + 1))
    c.line(MARGIN, top - 12, W - MARGIN, top - 12)
    for index, rail in enumerate(("L1", "L2", "L3")):
        y = top - 40 - 14 * index
        c.setLineWidth(1.2)
        c.line(MARGIN + 30, y, W - MARGIN - 20, y)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(MARGIN + 8, y - 3, rail)
    for col, tag, text in DEVICES[sheet - 1]:
        x, y = col_x(col), 230
        c.setLineWidth(0.9)
        c.rect(x - 13, y - 13, 26, 26)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(x - 16, y - 3, tag)
        c.setFont("Helvetica", 7)
        c.drawString(x + 16, y + 2, text)
    c.setFont("Helvetica", 7)
    for col, y, ref in XREFS[sheet - 1]:
        c.drawString(col_x(col), y, ref)
        if field is field_eplan:
            c.drawString(col_x(col), y - 10, f"=ANL+ORT{ref}")
    if sheet in NOTES:
        c.drawString(col_x(1), 112, NOTES[sheet])
    _title_block(c, TITLES[sheet - 1])
    field(c, sheet)


def build(out: Path, field: Callable[[canvas.Canvas, int], None]) -> None:
    c = canvas.Canvas(str(out), pagesize=(W, H), invariant=1)
    c.setTitle(f"Schriftfeld-Fixture {out.stem}")
    cover(c)
    c.showPage()
    contents(c)
    c.showPage()
    for sheet in range(1, TOTAL + 1):
        draw_sheet(c, sheet, field)
        c.showPage()
    c.save()


def gold() -> dict[str, dict[str, int]]:
    """Seite -> Blatt je Datei, so wie gezeichnet (Deckblatt und Inhaltsverzeichnis haben kein Blatt)."""
    pages = {str(FRONT_PAGES + sheet): sheet for sheet in range(1, TOTAL + 1)}
    return {name: dict(pages) for name in VARIANTS}


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else TARGET
    target.mkdir(parents=True, exist_ok=True)
    for name, field in VARIANTS.items():
        build(target / name, field)
        print(f"geschrieben: {target / name}")
    (target / "gold.json").write_text(json.dumps(gold(), indent=2) + "\n", encoding="utf-8")
    print(f"geschrieben: {target / 'gold.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
