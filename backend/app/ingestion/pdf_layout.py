"""Blatt und Spalten eines Stromlaufplans aus der PDF-Textebene (ohne Vision).

EPLAN-Verweise wie /3.8 bedeuten Blatt 3, Spalte 8. Das Blatt steht im Schriftfeld
("Blatt 3 / 7"), die Spaltennummern 1..N in der Kopfzeile des Zeichnungsrahmens. Positionen
werden relativ (0..1) zum gerenderten Seitenbild zurueckgegeben, Ursprung oben links.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion.vision import pdfium_lock

SHEET_RE = re.compile(r"Blatt\s+(\d+)\s*(?:/|von)\s*\d+", re.I)
MIN_COLUMNS = 4
TITLE_BLOCK_START = 0.75  # Schriftfeld liegt im untersten Viertel
FALLBACK_BOTTOM = 0.85


@dataclass(frozen=True)
class Column:
    n: int
    x0: float
    x1: float
    y0: float
    y1: float


@dataclass
class _Token:
    text: str
    left: float
    right: float
    top: float  # relativ, Ursprung oben
    bottom: float


def parse_ref(ref: str) -> tuple[int | None, int | None, int | None]:
    """'/3.8' -> (3, 8, None); 'S. 12' -> (None, None, 12); sonst (None, None, None)."""
    sheet = column = page = None
    if match := re.search(r"/(\d+)\.(\d+)", ref):
        sheet, column = int(match.group(1)), int(match.group(2))
    if match := re.search(r"S\.\s*(\d+)", ref):
        page = int(match.group(1))
    return sheet, column, page


@lru_cache(maxsize=32)
def _sheet_map(path: str, mtime: float) -> tuple[dict[int, int], int]:
    """Blatt -> Seite aus den Schriftfeldern, einmal je Datei(stand); dazu die Seitenzahl."""
    with pdfium_lock:
        pdf = pdfium.PdfDocument(path)
        try:
            sheets: dict[int, int] = {}
            for index in range(len(pdf)):
                match = SHEET_RE.search(pdf[index].get_textpage().get_text_range())
                if match:
                    sheets.setdefault(int(match.group(1)), index + 1)
            return sheets, len(pdf)
        finally:
            pdf.close()


def known_sheets(path: Path) -> set[int]:
    """Blattnummern des Plans (Schriftfeld), sonst 1..Seitenzahl."""
    sheets, pages = _sheet_map(str(path), path.stat().st_mtime)
    return set(sheets) if sheets else set(range(1, pages + 1))


def sheet_page(path: Path, sheet: int) -> int | None:
    """PDF-Seite (1-basiert) mit "Blatt {sheet}"; ohne Blatt-Beschriftung gilt Seite = Blatt."""
    sheets, pages = _sheet_map(str(path), path.stat().st_mtime)
    if sheets:
        return sheets.get(sheet)
    return sheet if 1 <= sheet <= pages else None


def _tokens(page: pdfium.PdfPage) -> list[_Token]:
    width, height = page.get_size()
    textpage = page.get_textpage()
    tokens: list[_Token] = []
    current: _Token | None = None
    for index in range(textpage.count_chars()):
        char = textpage.get_text_range(index, 1)
        if not char.strip():
            current = None
            continue
        left, bottom, right, top = textpage.get_charbox(index)
        box = _Token(char, left / width, right / width, 1 - top / height, 1 - bottom / height)
        if current and abs(box.top - current.top) < 0.005 and box.left - current.right < 0.006:
            current.text += char
            current.right = box.right
            current.bottom = max(current.bottom, box.bottom)
        else:
            current = box
            tokens.append(current)
    return tokens


def page_columns(path: Path, page: int) -> list[Column]:
    """Spalten 1..N aus der Kopfzeile; leer, wenn keine erkennbare Nummerierung."""
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            if not 1 <= page <= len(pdf):
                return []
            tokens = _tokens(pdf[page - 1])
        finally:
            pdf.close()

    numbers = [t for t in tokens if t.text.isdigit() and t.top < 1 / 3]
    rows: list[list[_Token]] = []
    for token in sorted(numbers, key=lambda t: t.top):
        if rows and abs(token.top - rows[-1][0].top) < 0.006:
            rows[-1].append(token)
        else:
            rows.append([token])
    best: list[_Token] = []
    for row in rows:
        row.sort(key=lambda t: t.left)
        sequence = [t for t in row if t.text.isdigit()]
        # laengste Folge 1, 2, 3 ... von links
        run: list[_Token] = []
        for token in sequence:
            if int(token.text) == len(run) + 1:
                run.append(token)
        if len(run) > len(best):
            best = run
    if len(best) < MIN_COLUMNS:
        return []

    centers = [(t.left + t.right) / 2 for t in best]
    half = (centers[-1] - centers[0]) / (len(centers) - 1) / 2
    bounds = [centers[0] - half] + [(a + b) / 2 for a, b in zip(centers, centers[1:], strict=False)] + [centers[-1] + half]
    top = min(t.top for t in best)
    title = [t.top for t in tokens if t.top > TITLE_BLOCK_START]
    bottom = min(title) - 0.01 if title else FALLBACK_BOTTOM
    return [
        Column(n=i + 1, x0=max(bounds[i], 0.0), x1=min(bounds[i + 1], 1.0), y0=max(top - 0.01, 0.0), y1=bottom)
        for i in range(len(best))
    ]
