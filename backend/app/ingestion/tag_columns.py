"""Spalte je Geraetekennzeichen auf einer Stromlaufplan-Seite, fuer den Antwortblock "Im Plan".

Die Spalten kommen aus der Kopfzeile des Zeichnungsrahmens (pdf_layout.page_columns), die Woerter aus derselben
Textebene in derselben Lage (ungedreht, relativ 0..1). Es zaehlen nur Woerter zwischen Kopfzeile und Schriftfeld.
Steht ein Kennzeichen mehrmals auf der Seite (Spule und Kontakte), gilt die Spalte, in der es am haeufigsten steht,
bei Gleichstand die linke. Ohne Spaltenraster ist das Ergebnis leer. Je (Pfad, Dateistand, Seite) einmal gerechnet.
"""

from collections import Counter
from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion.pdf_layout import Column, _tokens, page_columns
from app.ingestion.tags import TagType, extract_tags
from app.ingestion.vision import pdfium_lock


def _column_at(x: float, columns: list[Column]) -> int:
    """Spalte, in der x liegt; ausserhalb des Rasters die naechste."""
    return min(columns, key=lambda c: (max(c.x0 - x, x - c.x1, 0.0), c.n)).n


@lru_cache(maxsize=256)
def _tag_columns(path: str, mtime: float, page: int) -> tuple[tuple[str, int], ...]:
    """mtime nur als Cache-Schluessel; Tupel, damit der Cache-Inhalt unveraenderlich bleibt."""
    columns = page_columns(Path(path), page)
    if not columns:
        return ()
    with pdfium_lock:
        pdf = pdfium.PdfDocument(path)
        try:
            tokens = _tokens(pdf[page - 1])
        finally:
            pdf.close()
    top, bottom = min(c.y0 for c in columns), max(c.y1 for c in columns)
    counts: dict[str, Counter[int]] = {}
    for token in tokens:
        if not top <= (token.top + token.bottom) / 2 <= bottom:
            continue
        x = (token.left + token.right) / 2
        for tag in extract_tags(token.text):
            if tag.tag_type == TagType.DEVICE:
                counts.setdefault(tag.tag, Counter())[_column_at(x, columns)] += 1
    return tuple(
        sorted((tag, min(found, key=lambda n: (-found[n], n))) for tag, found in counts.items())
    )


def tag_columns(path: Path, page: int) -> dict[str, int]:
    """{Kennzeichen: Spaltennummer der Kopfzeile} einer PDF-Seite (1-basiert); leer ohne Spaltenraster."""
    return dict(_tag_columns(str(path), path.stat().st_mtime, page))
