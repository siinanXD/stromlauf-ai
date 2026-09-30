"""Blatt und Spalten eines Stromlaufplans aus der PDF-Textebene (ohne Vision).

EPLAN-Verweise wie /3.8 bedeuten Blatt 3, Spalte 8. Das Blatt steht im Schriftfeld ("Blatt 3 / 7", "Bl. 3",
"Sheet 3 of 7", "Folio : 3", "=ANL+ORT/3"), die Spaltennummern 1..N in der Kopfzeile des Zeichnungsrahmens.
Positionen werden relativ (0..1) zum gerenderten Seitenbild zurueckgegeben, Ursprung oben links.

Die Blatt-Map (Issue #67) liest nur das untere Viertel der Seite in Leserichtung, damit Querverweise und
Inhaltsverzeichnisse im Plan nicht als Blatt zaehlen. Wo sie keine Nummer findet, nimmt sie das Blatt an (ohne
Schriftfeld Seite = Blatt, sonst aus der Seitenfolge) und markiert das, statt still falsch zu verlinken.
"""

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.ingestion.vision import pdfium_lock

MIN_COLUMNS = 4
ROW_TOLERANCE = 0.006  # Hoehenversatz zweier benachbarter Spaltennummern, relativ zur Seitenhoehe
TITLE_BLOCK_START = 0.75  # Schriftfeld liegt im untersten Viertel
FALLBACK_BOTTOM = 0.85
SEGMENT_GAP = 0.03  # groesserer Abstand in einer Zeile trennt zwei Felder des Schriftfelds
FIELD_BELOW = 0.05  # Nummer unter einem allein stehenden Feldnamen, hoechstens so weit darunter
ALIGNED = 0.02  # Feldnamen mit hoechstens diesem Versatz stehen in derselben Spalte

_LABEL = r"(?:Blatt|Bl\.|Seite|Sheet|Page|Folio)"
# "Blatt 3 / 7", "Blatt 3 von 7", "Sheet 3 of 7", "Folio : 3", "Bl. 3"
_LABELED = re.compile(
    rf"(?<![\w.])({_LABEL})\s*(:)?\s*(\d{{1,4}})(?:\s*(?:/|von|of)\s*(\d{{1,4}}))?(?![\w.])", re.I
)
_LABEL_ALONE = re.compile(rf"^({_LABEL})\s*:?$", re.I)
_VALUE = re.compile(r"^(\d{1,4})(?:\s*(?:/|von|of)\s*(\d{1,4}))?(?![\w.])", re.I)
# EPLAN-Seitenname "=ANL+ORT/3"; Querverweise "=ANL+ORT/3.8" haben eine Spalte und zaehlen nicht
_PAGE_NAME = re.compile(r"(?<!\S)[^\s/]*[=+][^\s/]*/(\d{1,4})(?![\w./])")


@dataclass(frozen=True)
class Column:
    n: int
    x0: float
    x1: float
    y0: float
    y1: float


@dataclass(frozen=True)
class SheetPage:
    """Seite eines Blatts; guessed: nicht aus dem Schriftfeld gelesen, sondern angenommen (Seite = Blatt oder
    aus der Seitenfolge). page None heisst: Blatt nicht gefunden."""

    page: int | None
    guessed: bool = False


@dataclass(frozen=True)
class SheetMap:
    """Blatt je Seite. read: aus dem Schriftfeld; guessed: angenommen; gaps: Seiten, die eine Blattnummer tragen
    muessten, aber keine eindeutige haben (ohne jede gelesene Nummer: alle Seiten)."""

    page_count: int
    read: dict[int, int] = field(default_factory=dict)
    guessed: dict[int, int] = field(default_factory=dict)
    gaps: tuple[int, ...] = ()

    @property
    def sheets(self) -> set[int]:
        return set(self.read.values()) | set(self.guessed.values())

    @property
    def page_sheets(self) -> dict[int, int]:
        """Blatt je Seite, gelesen oder angenommen; Deckblatt und Inhaltsverzeichnis fehlen."""
        return {**self.guessed, **self.read}

    def page_of(self, sheet: int) -> SheetPage:
        for page, number in sorted(self.read.items()):
            if number == sheet:
                return SheetPage(page)
        for page, number in sorted(self.guessed.items()):
            if number == sheet:
                return SheetPage(page, guessed=True)
        # ohne jede gelesene Nummer ist auch "nicht gefunden" nur angenommen
        return SheetPage(None, guessed=not self.read)


@dataclass
class _Token:
    text: str
    left: float
    right: float
    top: float  # relativ, Ursprung oben
    bottom: float


@dataclass(frozen=True)
class _Candidate:
    sheet: int
    strength: int  # 4 EPLAN-Seitenname, 3 mit Blattanzahl, 2 mit Doppelpunkt, 1 nur Nummer
    label: str  # Feldname, klein und ohne Punkt
    left: float
    top: float
    total: int | None = None


def parse_ref(ref: str) -> tuple[int | None, int | None, int | None]:
    """'/3.8' -> (3, 8, None); 'S. 12' -> (None, None, 12); sonst (None, None, None)."""
    sheet = column = page = None
    if match := re.search(r"/(\d+)\.(\d+)", ref):
        sheet, column = int(match.group(1)), int(match.group(2))
    if match := re.search(r"S\.\s*(\d+)", ref):
        page = int(match.group(1))
    return sheet, column, page


def _text_angle(textpage: pdfium.PdfTextPage) -> int:
    """Haeufigste Schreibrichtung der Zeichen, auf 90 Grad gerundet. pdfium zaehlt im Uhrzeigersinn: 270 heisst,
    der Text laeuft auf der Seite nach oben (Blatt gegen den Uhrzeigersinn gedreht)."""
    counts: dict[int, int] = {}
    for index in range(textpage.count_chars()):
        angle = pdfium_c.FPDFText_GetCharAngle(textpage.raw, index)
        if angle >= 0:
            key = round(math.degrees(angle) / 90) % 4 * 90
            counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.__getitem__) if counts else 0


def _char_box(
    textpage: pdfium.PdfTextPage, index: int, width: float, height: float, angle: int
) -> tuple[float, float, float, float]:
    """(links, rechts, oben, unten) relativ in Leserichtung, Ursprung oben links."""
    left, bottom, right, top = textpage.get_charbox(index)
    if angle == 90:  # Text laeuft nach unten
        return (
            (height - top) / height,
            (height - bottom) / height,
            (width - right) / width,
            (width - left) / width,
        )
    if angle == 180:
        return (width - right) / width, (width - left) / width, bottom / height, top / height
    if angle == 270:  # Text laeuft nach oben
        return bottom / height, top / height, left / width, right / width
    return left / width, right / width, 1 - top / height, 1 - bottom / height


def _tokens(page: pdfium.PdfPage, angle: int = 0, start: float = 0.0) -> list[_Token]:
    """Woerter der Seite in Leserichtung `angle`; nur Zeichen ab der relativen Hoehe `start`."""
    width, height = page.get_size()
    textpage = page.get_textpage()
    tokens: list[_Token] = []
    current: _Token | None = None
    for index in range(textpage.count_chars()):
        char = chr(pdfium_c.FPDFText_GetUnicode(textpage.raw, index))
        if not char.strip():
            current = None
            continue
        left, right, top, bottom = _char_box(textpage, index, width, height, angle)
        if top < start:
            current = None
            continue
        box = _Token(char, left, right, top, bottom)
        # gleiche Zeile heisst ueberlappende Hoehe: Punkt und Strich sitzen tiefer als Buchstaben ("Bl.", "-K1")
        if (
            current
            and min(current.bottom, box.bottom) > max(current.top, box.top)
            and box.left - current.right < 0.006
        ):
            current.text += char
            current.right = box.right
            current.top = min(current.top, box.top)
            current.bottom = max(current.bottom, box.bottom)
        else:
            current = box
            tokens.append(current)
    return tokens


def _segments(tokens: list[_Token]) -> list[list[_Token]]:
    """Woerter derselben Zeile mit kleinem Abstand: ein Feld des Schriftfelds. Gleiche Zeile heisst ueberlappende
    Hoehe, weil Feldname und Nummer oft verschieden grosse Schrift haben."""
    segments: list[list[_Token]] = []
    for token in sorted(tokens, key=lambda t: t.left):
        for segment in segments:
            last = segment[-1]
            overlap = min(last.bottom, token.bottom) - max(last.top, token.top)
            smaller = max(min(last.bottom - last.top, token.bottom - token.top), 1e-6)
            if overlap >= 0.5 * smaller and -0.005 <= token.left - last.right < SEGMENT_GAP:
                segment.append(token)
                break
        else:
            segments.append([token])
    return segments


def _text(segment: list[_Token]) -> str:
    return " ".join(token.text for token in segment)


def _value_below(label: list[_Token], segments: list[list[_Token]]) -> re.Match | None:
    """Nummer unter einem allein stehenden Feldnamen ("Blatt" klein oben im Feld, "3 von 7" darunter)."""
    bottom = max(t.bottom for t in label)
    left, right = label[0].left - ALIGNED, label[-1].right + ALIGNED
    below = [
        segment
        for segment in segments
        if bottom - 0.005 <= segment[0].top <= bottom + FIELD_BELOW
        and segment[0].left < right
        and segment[-1].right > left
    ]
    for segment in sorted(below, key=lambda s: s[0].top):
        if match := _VALUE.match(_text(segment)):
            return match
    return None


def _candidates(tokens: list[_Token]) -> list[_Candidate]:
    segments = _segments(tokens)
    found: list[_Candidate] = []
    for segment in segments:
        text = _text(segment)
        left, top = segment[0].left, min(t.top for t in segment)
        for match in _PAGE_NAME.finditer(text):
            found.append(_Candidate(int(match.group(1)), 4, "=", left, top))
        for match in _LABELED.finditer(text):
            label, colon, number, total = match.groups()
            # ohne Blattanzahl zaehlt nur ein Feld, das nichts anderes enthaelt: "von Blatt 3" ist ein Hinweis
            if not total and (match.start() > 0 or match.end() < len(text)):
                continue
            strength = 3 if total else 2 if colon else 1
            name = label.lower().rstrip(".")
            found.append(
                _Candidate(int(number), strength, name, left, top, int(total) if total else None)
            )
        if (alone := _LABEL_ALONE.match(text)) and (value := _value_below(segment, segments)):
            total = int(value.group(2)) if value.group(2) else None
            name = alone.group(1).lower().rstrip(".")
            found.append(_Candidate(int(value.group(1)), 3 if total else 1, name, left, top, total))
    return found


def _page_sheet(candidates: list[_Candidate]) -> _Candidate | None:
    """Blattnummer einer Seite aus ihren Kandidaten im Schriftfeld; None, wenn keine eindeutig ist."""
    if not candidates:
        return None
    best = max(c.strength for c in candidates)
    strongest = [c for c in candidates if c.strength == best]
    if len({c.sheet for c in strongest}) == 1:
        return strongest[0]
    lefts = [c.left for c in strongest]
    if len({c.label for c in strongest}) == 1 and max(lefts) - min(lefts) < ALIGNED:
        upper, *rest = sorted(strongest, key=lambda c: c.top)
        # QElectroTech zeigt unter "Folio : 4" mit demselben Feldnamen das Folgeblatt "Folio : 5"
        if len(rest) == 1 and best >= 2 and rest[0].sheet == upper.sheet + 1:
            return upper
        return None  # untereinander stehende "Blatt n": eine Liste wie ein Inhaltsverzeichnis, kein Schriftfeld
    # Hinweise der Zeichnung stehen ueber dem Schriftfeld
    return max(strongest, key=lambda c: c.top)


def _page_label(page: pdfium.PdfPage) -> _Candidate | None:
    angle = _text_angle(page.get_textpage())
    return _page_sheet(_candidates(_tokens(page, angle, TITLE_BLOCK_START)))


def _without_strays(labels: dict[int, int]) -> dict[int, int]:
    """Traegt dieselbe Nummer mehrere Seiten, zaehlt die, die zwischen ihre Nachbarn passt. So faellt etwa die letzte
    Zeile eines Inhaltsverzeichnisses heraus, die ins untere Viertel reicht; sonst gilt die erste Seite."""
    ordered = sorted(labels)
    kept = dict(labels)
    for sheet in set(labels.values()):
        pages = [page for page in ordered if labels[page] == sheet]
        if len(pages) < 2:
            continue

        def fits(page: int, sheet: int = sheet) -> bool:
            index = ordered.index(page)
            before = labels[ordered[index - 1]] if index else None
            after = labels[ordered[index + 1]] if index + 1 < len(ordered) else None
            return (before is None or before < sheet) and (after is None or after > sheet)

        keep = next((page for page in pages if fits(page)), pages[0])
        for page in pages:
            if page != keep:
                del kept[page]
    return kept


def _build_map(labels: dict[int, int], totals: list[int], page_count: int) -> SheetMap:
    """Gelesene Nummern plus Annahmen fuer die Seiten, die eine tragen muessten: zwischen gelesenen Seiten, vor der
    ersten, wenn sie nicht Blatt 1 ist, und nach der letzten bis zur Blattanzahl ("von 7")."""
    if not labels:
        pages = tuple(range(1, page_count + 1))
        return SheetMap(page_count, {}, {page: page for page in pages}, pages)
    ordered = sorted(labels)
    first, last = ordered[0], ordered[-1]
    gaps = [page for page in range(max(1, first - (labels[first] - 1)), first)]
    gaps += [page for page in range(first + 1, last) if page not in labels]
    gaps += list(range(last + 1, min(page_count, last + max(totals, default=0) - labels[last]) + 1))
    known = set(labels.values())
    guessed: dict[int, int] = {}
    for page in gaps:
        below = max((p for p in ordered if p < page), default=None)
        above = min((p for p in ordered if p > page), default=None)
        low = labels[below] if below is not None else 0
        high = labels[above] if above is not None else math.inf
        options = []
        if below is not None:
            options.append(low + page - below)
        if above is not None:
            options.append(labels[above] - (above - page))
        # das Blatt muss zwischen die gelesenen Nachbarn passen und darf nicht schon gelesen sein
        sheet = next((s for s in options if low < s < high and s not in known), None)
        if sheet is not None:
            guessed[page] = sheet
    return SheetMap(page_count, dict(labels), guessed, tuple(gaps))


@lru_cache(maxsize=32)
def _sheet_map(path: str, mtime: float) -> SheetMap:
    """Blatt-Map einmal je Datei(stand)."""
    with pdfium_lock:
        pdf = pdfium.PdfDocument(path)
        try:
            labels: dict[int, int] = {}
            totals: list[int] = []
            for index in range(len(pdf)):
                if label := _page_label(pdf[index]):
                    labels[index + 1] = label.sheet
                    if label.total:
                        totals.append(label.total)
            return _build_map(_without_strays(labels), totals, len(pdf))
        finally:
            pdf.close()


def sheet_map(path: Path) -> SheetMap:
    return _sheet_map(str(path), path.stat().st_mtime)


def known_sheets(path: Path) -> set[int]:
    """Blattnummern des Plans, gelesen oder angenommen (ohne Schriftfeld 1..Seitenzahl)."""
    return sheet_map(path).sheets


def sheet_page(path: Path, sheet: int) -> SheetPage:
    """PDF-Seite (1-basiert) eines Blatts und ob sie nur angenommen ist."""
    return sheet_map(path).page_of(sheet)


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

    # Laengste Folge 1, 2, 3 ... von links. Nur Nachbarn muessen auf gleicher Hoehe liegen, nicht die ganze Zeile:
    # Ein 0,5 Grad schief eingescannter Plan faellt ueber die Blattbreite um etwa 0,012 ab (Issue #65).
    numbers = sorted(
        (t for t in tokens if t.text.isdigit() and t.top < 1 / 3), key=lambda t: t.left
    )
    best: list[_Token] = []
    for start in (t for t in numbers if t.text == "1"):
        run = [start]
        for token in numbers:
            if (
                token.left > run[-1].left
                and int(token.text) == len(run) + 1
                and abs(token.top - run[-1].top) < ROW_TOLERANCE
            ):
                run.append(token)
        if len(run) > len(best):
            best = run
    if len(best) < MIN_COLUMNS:
        return []

    centers = [(t.left + t.right) / 2 for t in best]
    half = (centers[-1] - centers[0]) / (len(centers) - 1) / 2
    bounds = (
        [centers[0] - half]
        + [(a + b) / 2 for a, b in zip(centers, centers[1:], strict=False)]
        + [centers[-1] + half]
    )
    top = min(t.top for t in best)
    title = [t.top for t in tokens if t.top > TITLE_BLOCK_START]
    bottom = min(title) - 0.01 if title else FALLBACK_BOTTOM
    return [
        Column(
            n=i + 1,
            x0=max(bounds[i], 0.0),
            x1=min(bounds[i + 1], 1.0),
            y0=max(top - 0.01, 0.0),
            y1=bottom,
        )
        for i in range(len(best))
    ]
