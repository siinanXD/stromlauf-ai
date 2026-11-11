"""Vertrauensmass je Seite (SIN-1226, Schritt 1 des Modell-Rueckfalls aus Issue #122).

Keine neue Leseregel: `confidence` misst, wie viel die eingefrorenen Regeln auf einer Seite gelesen haben, als Zahl
von 0 bis 1 aus vier Anteilen. `read_pages` holt die vier Groessen mit denselben Funktionen, die der Upload nutzt,
ohne Datenbank und Modell. Seiten unter `THRESHOLD` sind Kandidaten fuer den Rueckfall (ab SIN-1227).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion import pdf_layout, plan_wires
from app.ingestion.tags import detect_folio_style, detect_spaced_terminals, extract_tags
from app.ingestion.vision import pdfium_lock

# Gleich gewichtet: Issue #122 nennt genau diese vier Groessen und keine Rangfolge.
WEIGHT_SHEET = WEIGHT_HEADER = WEIGHT_TAGS = WEIGHT_ENDS = 0.25
# Ab einem Kennzeichen je zehn Woerter zaehlt der Kennzeichen-Anteil voll. Gemessen an FB-01, UR-01 und PM1-AR:
# 0,11 (Einspeisung, Uebersicht) bis 0,47 (Stuecklistenseiten); darunter liegt Fliesstext oder ein fremdes Format.
TAG_SHARE = 0.10
# Fehlt einer der vier Anteile ganz, erreicht die Seite hoechstens 0,75 und faellt unter die Schwelle. Die
# schwaechste Seite der drei Beispielanlagen (FB-01 Blatt 3: 27 von 48 Netzenden benannt) liegt bei 0,89.
# Derselbe Wert steht als Vorgabe von PAGE_READER_THRESHOLD in app/config.py (Test haelt beide gleich).
THRESHOLD = 0.8


@dataclass(frozen=True)
class PageReading:
    """Was die Regeln auf einer Seite gelesen haben."""

    sheet_read: bool = False  # Blattnummer aus dem Schriftfeld gelesen, nicht angenommen
    header: bool = False  # Spaltenraster aus der Kopfzeile erkannt
    tags: int = 0  # verschiedene Kennzeichen im Seitentext
    words: int = 0
    ends: int = 0  # freie Enden der Leitungsnetze, ohne durchlaufende Schienen
    named_ends: int = 0


def confidence(reading: PageReading) -> float:
    """0 (nichts gelesen) bis 1 (alles gelesen). Eine Seite ohne Leitungsenden hat keine unbenannten: Der Anteil
    zaehlt dann voll, sonst fielen Deckblatt und Stuecklistenseiten immer unter die Schwelle."""
    tags = min(1.0, reading.tags / reading.words / TAG_SHARE) if reading.words else 0.0
    ends = reading.named_ends / reading.ends if reading.ends else 1.0
    return (
        WEIGHT_SHEET * reading.sheet_read
        + WEIGHT_HEADER * reading.header
        + WEIGHT_TAGS * tags
        + WEIGHT_ENDS * ends
    )


def _ends(path: Path, page: int, spaced: bool) -> tuple[int, int]:
    """Freie Netzenden der Seite und wie viele davon einen Namen tragen; Namen wie in plan_wires._wire_edges."""
    geometry = plan_wires._geometry(path, page)
    if geometry is None:
        return 0, 0
    spots = list(geometry.spots)
    anchors = plan_wires._anchors(spots, spaced)
    runs = plan_wires._terminal_runs(spots, spaced)
    terminals = plan_wires._listed_terminals(
        [run for run, alone in runs if alone], geometry.boxes, anchors
    )
    listed = {id(spot) for run, _alone in runs for _node, spot in run}
    anchors = [anchor for anchor in anchors if id(anchor.spot) not in listed]
    nets = plan_wires.page_nets(list(geometry.segments), geometry.dots)
    names = plan_wires._end_names(
        nets,
        plan_wires._Boxes(geometry.boxes),
        anchors,
        plan_wires._box_labels(geometry.boxes, spots),
        terminals,
    )
    # Schienen (L1, N, PE ueber die halbe Seite) bilden in plan_wires keine Kanten; ihre Enden zaehlen nicht
    rows = [
        row
        for net, row in zip(nets, names, strict=True)
        if not plan_wires._is_rail(net, geometry.size)
    ]
    return sum(len(row) for row in rows), sum(1 for row in rows for name in row if name)


def read_pages(path: Path) -> dict[int, PageReading]:
    """Lesestand je Seite (1-basiert) eines Plan-PDFs."""
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            texts = [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
        finally:
            pdf.close()
    whole = "\n".join(texts)
    folio, spaced = detect_folio_style(whole), detect_spaced_terminals(whole)
    sheets = pdf_layout.sheet_map(path).read
    pages = {}
    for page, text in enumerate(texts, start=1):
        ends, named = _ends(path, page, spaced)
        pages[page] = PageReading(
            sheet_read=page in sheets,
            header=bool(pdf_layout.page_columns(path, page)),
            tags=len(extract_tags(text, folio_style=folio, spaced_terminals=spaced)),
            words=len(text.split()),
            ends=ends,
            named_ends=named,
        )
    return pages
