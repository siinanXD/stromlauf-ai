"""Leitungen aus Stromlaufplan-PDFs lesen: Segmente, Netze, benannte Enden und Kanten (Stoerfall-Arbeitsflaeche).

Ablauf je Seite, deterministisch und ohne Modell:

1. `page_segments`: Vektorlinien ueber die pypdfium2-Rohschnittstelle. Jede Objektmatrix wird angewendet, auch
   verschachtelt in Form-XObjects; Bezierkurven werden in CHORDS Sehnen zerlegt. Koordinaten in pt, Ursprung oben
   links, in derselben Leserichtung wie die Wortpositionen von `pdf_layout._spots` (gedrehte Blaetter).
   Weg fallen Rahmen, Spaltenkopf und Schriftfeld (Grenzen wie `pdf_layout.page_columns` und TITLE_BAND),
   geschlossene Pfade (Symbole), schraege Striche (Kontaktzunge, Kreuz einer Leuchte) und, wenn ein Dokument Leiter
   und Symbole ueber die Strichstaerke trennt, alles ausser der Leiterstaerke.
2. `page_nets`: Endpunkte naeher als SNAP rasten ein (cKDTree), ein Endpunkt auf dem Inneren eines anderen Segments
   ist ein T-Abzweig. Eine Kreuzung verbindet nur mit Verbindungspunkt (gefuellter Pfad bis DOT_MAX). Netze sind die
   Zusammenhangskomponenten (networkx); freie Enden sind Endpunkte ohne Anschluss an ein anderes Segment.
3. `page_wire_edges`: Jedes freie Ende sucht den naechsten Anschluss-Text: Geraeteanschluss wie in #102
   (`pdf_layout.pin_spots`), Klemme ("-X1:3", "X420 3") oder SPS-Adresse (E/A). Es gelten PIN_REACH und PIN_CLEAR.
   Klemmen und Adressen zaehlen nur am Anfang ihrer Zeile ("0 V ueber -X3:14" ist ein Hinweis). Dazu diese Regeln:
   - Endet eine Leitung am Rand eines grossen Symbols (SPS-Karte, Geraet, Leuchte), gilt nur die Beschriftung im
     Symbol auf derselben Hoehe; daneben stehen Texte anderer Zeilen. Steht im Symbol keine, gilt das Kennzeichen
     neben dem Symbol (links oder rechts auf seiner Hoehe, bis LABEL_GAP), ausser am Symbol stehen
     Anschlussnummern (Spule A1/A2). Ein Anschluss schlaegt dabei sein Geraet ("-K1:A1" und "-K1" in einem Netz).
   - Enden an derselben Klemme (kleines Symbol) teilen ihren Namen, die Beschriftung steht nur an einer Seite. Eine
     Beschriftung benennt nur Enden an der Klemme, der sie am naechsten steht.
   - Eine Zeile nur aus Klemmen einer Leiste ("-X4:U -X4:V -X4:W") benennt die Klemmen in ihrer Naehe (PIN_REACH)
     von links nach rechts, wenn es genau so viele in einer Reihe sind; Klemmen mit eigener Beschriftung zaehlen
     nicht mit. Eine Zeile mit mehreren Klemmen benennt nie ein Leitungsende nach Naehe.
   - Laeuft eine Leitung durch Klemme und Eingang hindurch (Kanaele in Spalten), gehoeren Klemmen und Adressen bis
     BESIDE neben ihr zu ihrem Netz.
   Ein Netz verbindet seine benannten Enden. Netze mit einer Leitung ueber mehr als RAIL_SHARE der Blattbreite oder
   mehr als MAX_ENDS benannten Enden sind Potentialschienen und ergeben keine Kanten (wie die Versorgung im
   Klemmenplan, `signal_graph.SUPPLY_WORDS`).
4. `plan_edges`: alle Seiten, mit Datei-Cache (`plan_edges.read_edges`/`write_edges`). Dazu die Lage im Plan
   (`via="lage"`) auf jeder Seite, mit und ohne Leiter: Kanaele in Spalten (#90) oder in Zeilen (Feldgeraet, Klemme
   und Adresse auf einer Linie +-ROW), wenn mindestens LAGE_MIN Kanaele so stehen. Eine Lage-Kante kommt nur dazu,
   wenn keine Leitung dieselben Knoten (oder Anschluss und Geraet) schon verbindet. Das Feldgeraet steht jenseits der
   Klemme, von der Adresse aus; eine Adresse in Klammern ist ein Verweis und keine Kanal-Adresse.

Richtung: Ein Netz mit E-Adresse laeuft zur Adresse, eins mit A-Adresse von ihr weg; eine Spule ist Ziel, ein Kontakt
Quelle, wie in `signal_graph._add_terminal_rows`. Alles andere bleibt ungerichtet (`directed=False`).
"""

from __future__ import annotations

import ctypes
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from scipy.spatial import cKDTree

from app.ingestion import pdf_layout
from app.ingestion.pdf_layout import PIN_CLEAR, PIN_REACH, TITLE_BAND, _Spot
from app.ingestion.plan_edges import PlanEdge, read_edges, write_edges
from app.ingestion.tags import TagType, detect_spaced_terminals, extract_tags, pin_kind
from app.ingestion.vision import pdfium_lock

SNAP = 1.0  # pt: Endpunkte und T-Abzweige rasten so nah ein
DOT_MAX = 4.0  # pt: groesster Durchmesser eines Verbindungspunkts
CHORDS = 4  # Sehnen je Bezierkurve
CONDUCTOR_MIN = 20  # Segmente je Strichstaerke, ab denen ein Dokument Leiter und Symbole ueber die Staerke trennt
LONG = 10.0  # pt: kuerzere Segmente zaehlen bei der Wahl der Leiterstaerke nicht
WIDTH_STEP = 0.05  # pt: Strichstaerken auf dieses Raster gerundet
AXIS = 0.035  # Steigung bis etwa 2 Grad gilt als waagerecht bzw. senkrecht; schraege Striche sind Symbole
EDGE = 0.003  # relativ: Linien auf dem Rand des Spaltenrasters sind Rahmen
HEADER_GAP = 0.01  # relativ: Spaltenkopf reicht so weit unter die Spaltennummern
# Leitung ueber mehr als diesen Anteil der Blattbreite oder -hoehe, oder mehr benannte Enden: Potentialschiene
RAIL_SHARE = 0.5
MAX_ENDS = 4
ROW = 3.0  # pt: gleiche Hoehe fuer Kanaele in Zeilen und fuer Beschriftungen im Symbol
# pt: groesste Seite eines Klemmensymbols; groessere Symbole sind Geraete, Karten, Leuchten
TERMINAL_MAX = 8.0
# pt: so nah steht eine Klemme oder Adresse an der Leitung, die durch sie hindurchlaeuft
BESIDE = 10.0
SKEW = 0.02  # Steigung einer Zeile auf einem schief eingescannten Blatt, etwa 1 Grad
LAGE_MIN = 3  # so viele Kanaele muss eine Seite ohne Leiter in Zeilen oder Spalten zeigen
SPACED_GAP = 10.0  # pt: "X420" und "3" stehen so nah nebeneinander (gemessen bis 9 pt)
LINE = 2.0  # pt: Woerter mit hoechstens diesem Hoehenversatz stehen in einer Zeile
PHRASE_GAP = 6.0  # pt: Woerter eines Satzes stehen hoechstens so weit auseinander
LABEL_GAP = 8.0  # pt: so weit steht das Kennzeichen neben seinem Symbol (gemessen 3 bis 6 pt)

_BIT = re.compile(r"[EA]\d+\.[0-7]")
_CARD = re.compile(r"-A\d+(\.\d+)?$")  # SPS-Karte: Ort der Adresse, kein Feldgeraet
_CABLE = re.compile(r"-W\d")  # Leitung (Kabel), kein Feldgeraet
_STRIP = re.compile(r"-X\d")  # Klemmleiste: benennt keine Symbole, ihre Klemmen tragen Nummern
_REFERENCE = re.compile(r"\([^()]*\)")  # Text in Klammern: Verweis, keine eigene Beschriftung

Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class Segment:
    """Gerades Stueck einer Linie in pt, Ursprung oben links, in Leserichtung der Seite."""

    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    dashed: bool = False

    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass(frozen=True)
class Net:
    """Zusammenhaengende Leitungen; ends sind die freien Enden (kein anderes Segment schliesst dort an)."""

    segments: tuple[Segment, ...]
    ends: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class _Box:
    """Geschlossener Pfad (Symbol) als Rechteck in Leserichtung."""

    x0: float
    y0: float
    x1: float
    y1: float

    def on_edge(self, x: float, y: float, tolerance: float = SNAP) -> str | None:
        """Seite des Rands, auf dem der Punkt liegt: "side" (links/rechts), "end" (oben/unten) oder None."""
        inside_y = self.y0 - tolerance <= y <= self.y1 + tolerance
        inside_x = self.x0 - tolerance <= x <= self.x1 + tolerance
        if inside_y and (abs(x - self.x0) <= tolerance or abs(x - self.x1) <= tolerance):
            return "side"
        if inside_x and (abs(y - self.y0) <= tolerance or abs(y - self.y1) <= tolerance):
            return "end"
        return None

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass(frozen=True)
class _Geometry:
    """Was eine Seite zeichnet, in Leserichtung: Segmente nach allen Filtern, Verbindungspunkte, Symbole, Woerter."""

    size: tuple[float, float]
    segments: tuple[Segment, ...]
    dots: tuple[tuple[float, float, float], ...]  # Mitte x, y und Radius
    boxes: tuple[_Box, ...]
    spots: tuple[_Spot, ...]


# --- Segmente ---------------------------------------------------------------------------------


def _then(inner: Matrix, outer: Matrix) -> Matrix:
    """Erst inner, dann outer (PDF-Zeilenvektoren: p * inner * outer)."""
    a1, b1, c1, d1, e1, f1 = inner
    a2, b2, c2, d2, e2, f2 = outer
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _matrix(obj) -> Matrix:
    raw = pdfium_c.FS_MATRIX()
    if not pdfium_c.FPDFPageObj_GetMatrix(obj, ctypes.byref(raw)):
        return IDENTITY
    return (raw.a, raw.b, raw.c, raw.d, raw.e, raw.f)


def _cubic(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
    )


def _subpaths(obj, m: Matrix) -> list[tuple[list[tuple[float, float]], bool]]:
    """Teilpfade eines Pfadobjekts als Punktfolgen in Seitenkoordinaten (PDF, Ursprung unten) und ob geschlossen."""
    shapes: list[tuple[list[tuple[float, float]], bool]] = []
    points: list[tuple[float, float]] | None = None
    closed = False
    curve: list[tuple[float, float]] = []
    x, y = ctypes.c_float(), ctypes.c_float()
    for index in range(pdfium_c.FPDFPath_CountSegments(obj)):
        segment = pdfium_c.FPDFPath_GetPathSegment(obj, index)
        if not segment or not pdfium_c.FPDFPathSegment_GetPoint(
            segment, ctypes.byref(x), ctypes.byref(y)
        ):
            continue
        point = _apply(m, x.value, y.value)
        kind = pdfium_c.FPDFPathSegment_GetType(segment)
        if kind == pdfium_c.FPDF_SEGMENT_MOVETO or points is None:
            if points is not None:
                shapes.append((points, closed))
            points, closed, curve = [point], False, []
        elif kind == pdfium_c.FPDF_SEGMENT_BEZIERTO:
            curve.append(point)
            if len(curve) == 3:
                start = points[-1]
                points += [_cubic(start, *curve, (i + 1) / CHORDS) for i in range(CHORDS)]
                curve = []
        else:
            points.append(point)
        if pdfium_c.FPDFPathSegment_GetClose(segment):
            closed = True
    if points is not None:
        shapes.append((points, closed))
    return shapes


def _dashed(obj) -> bool:
    count = pdfium_c.FPDFPageObj_GetDashCount(obj)
    if count <= 0:
        return False
    values = (ctypes.c_float * count)()
    if not pdfium_c.FPDFPageObj_GetDashArray(obj, values, count):
        return False
    return any(value > 0 for value in values)


def _path_objects(container, form: bool, m: Matrix):
    """(Pfadobjekt, Gesamtmatrix) aller Pfade, rekursiv durch Form-XObjects."""
    count = (pdfium_c.FPDFFormObj_CountObjects if form else pdfium_c.FPDFPage_CountObjects)(
        container
    )
    get = pdfium_c.FPDFFormObj_GetObject if form else pdfium_c.FPDFPage_GetObject
    for index in range(max(count, 0)):
        obj = get(container, index)
        if not obj:
            continue
        kind = pdfium_c.FPDFPageObj_GetType(obj)
        total = _then(_matrix(obj), m)
        if kind == pdfium_c.FPDF_PAGEOBJ_FORM:
            yield from _path_objects(obj, True, total)
        elif kind == pdfium_c.FPDF_PAGEOBJ_PATH:
            yield obj, total


def _to_reading(angle: int, width: float, height: float):
    """Seitenkoordinaten (PDF, Ursprung unten) -> pt in Leserichtung wie pdf_layout._char_box/_spots."""
    if angle == 90:
        return lambda x, y: (height - y, width - x)
    if angle == 180:
        return lambda x, y: (width - x, y)
    if angle == 270:
        return lambda x, y: (y, x)
    return lambda x, y: (x, height - y)


def _axis_aligned(x1: float, y1: float, x2: float, y2: float) -> bool:
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    return dy <= AXIS * dx or dx <= AXIS * dy


def _raw_drawing(page: pdfium.PdfPage, reading) -> tuple[list[Segment], list, list[_Box]]:
    """Offene Striche als Segmente, kleine gefuellte Pfade als Punkte, geschlossene Pfade als Symbole."""
    segments: list[Segment] = []
    dots: list[tuple[float, float, float]] = []
    boxes: list[_Box] = []
    fill, stroke, width = ctypes.c_int(), ctypes.c_int(), ctypes.c_float()
    for obj, m in _path_objects(page.raw, False, IDENTITY):
        pdfium_c.FPDFPath_GetDrawMode(obj, ctypes.byref(fill), ctypes.byref(stroke))
        if not fill.value and not stroke.value:
            continue  # Beschneidungspfad
        pdfium_c.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(width))
        scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        stroke_width = round(width.value * scale / WIDTH_STEP) * WIDTH_STEP
        dashed = _dashed(obj)
        for points, closed in _subpaths(obj, m):
            mapped = [reading(*point) for point in points]
            xs, ys = [p[0] for p in mapped], [p[1] for p in mapped]
            box = _Box(min(xs), min(ys), max(xs), max(ys))
            if (
                fill.value
                and box.x1 - box.x0 <= DOT_MAX
                and box.y1 - box.y0 <= DOT_MAX
                and len(mapped) > 2
            ):
                radius = max(box.x1 - box.x0, box.y1 - box.y0) / 2
                if radius > 0.2:
                    dots.append(((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, radius))
                continue
            if (
                closed
                or fill.value
                or (len(mapped) > 3 and math.dist(mapped[0], mapped[-1]) <= SNAP)
            ):
                boxes.append(box)
                continue
            if not stroke.value:
                continue
            for (x1, y1), (x2, y2) in zip(mapped, mapped[1:], strict=False):
                if math.dist((x1, y1), (x2, y2)) > 0:
                    segments.append(Segment(x1, y1, x2, y2, stroke_width, dashed))
    return segments, dots, boxes


def _frame_filter(
    segments: list[Segment], tokens: list, label, size: tuple[float, float]
) -> list[Segment]:
    """Rahmen, Spaltenkopf und Schriftfeld weg: Grenzen wie pdf_layout.page_columns und TITLE_BAND."""
    width, height = size
    columns, header = pdf_layout._column_grid(tokens)
    header_bottom = max(t.bottom for t in header) + HEADER_GAP if header else None
    title_top = label.top - TITLE_BAND if label else None
    left = columns[0].x0 if columns else None
    right = columns[-1].x1 if columns else None
    kept = []
    for s in segments:
        ys = (s.y1 / height, s.y2 / height)
        xs = (s.x1 / width, s.x2 / width)
        if header_bottom is not None and max(ys) <= header_bottom:
            continue
        if title_top is not None and min(ys) >= title_top:
            continue
        if left is not None and (max(xs) <= left + EDGE or min(xs) >= right - EDGE):
            continue
        kept.append(s)
    return kept


def _conductors(segments: list[Segment]) -> list[Segment]:
    """Trennt ein Dokument Leiter und Symbole ueber die Strichstaerke (je CONDUCTOR_MIN Segmente in mindestens zwei
    Staerken), bleibt nur die Staerke mit den meisten langen Segmenten."""
    solid = [s for s in segments if not s.dashed]
    counts = Counter(s.width for s in solid)
    if sum(1 for n in counts.values() if n >= CONDUCTOR_MIN) < 2:
        return segments
    long = Counter(s.width for s in solid if s.length >= LONG)
    if not long:
        return segments
    best = max(sorted(long), key=lambda w: long[w])
    return [s for s in segments if s.dashed or abs(s.width - best) < WIDTH_STEP / 2]


def _read_geometry(page: pdfium.PdfPage) -> _Geometry:
    textpage = page.get_textpage()
    angle = pdf_layout._text_angle(textpage)
    width, height = page.get_size()
    size = (height, width) if angle in (90, 270) else (width, height)
    reading = _to_reading(angle, width, height)
    raw, dots, boxes = _raw_drawing(page, reading)
    straight = [s for s in raw if _axis_aligned(s.x1, s.y1, s.x2, s.y2)]
    tokens = pdf_layout._tokens(page, angle)
    label = pdf_layout._page_label(page)
    segments = _conductors(_frame_filter(straight, tokens, label, size))
    spots = pdf_layout._spots(page)
    return _Geometry(size, tuple(segments), tuple(dots), tuple(boxes), tuple(spots))


@lru_cache(maxsize=64)
def _geometry_cached(path: str, mtime_ns: int, size: int, page: int) -> _Geometry | None:
    with pdfium_lock:
        pdf = pdfium.PdfDocument(path)
        try:
            if not 1 <= page <= len(pdf):
                return None
            return _read_geometry(pdf[page - 1])
        finally:
            pdf.close()


def _geometry(path: Path, page: int) -> _Geometry | None:
    stat = Path(path).stat()
    return _geometry_cached(str(path), stat.st_mtime_ns, stat.st_size, page)


def page_segments(path: Path, page: int) -> list[Segment]:
    """Leiter-Segmente einer Seite (1-basiert) in pt, Ursprung oben links, in Leserichtung; [] ohne Seite."""
    geometry = _geometry(path, page)
    return list(geometry.segments) if geometry else []


# --- Netze ------------------------------------------------------------------------------------


def _point_segment(px: float, py: float, s: Segment) -> float:
    dx, dy = s.x2 - s.x1, s.y2 - s.y1
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - s.x1) * dx + (py - s.y1) * dy) / span))
    return math.hypot(px - (s.x1 + t * dx), py - (s.y1 + t * dy))


class _Grid:
    """Segmente je Rasterzelle, um Punkte in ihrer Naehe ohne Vergleich mit allen zu finden."""

    CELL = 16.0

    def __init__(self, segments: list[Segment], reach: float):
        self.cells: dict[tuple[int, int], list[int]] = defaultdict(list)
        for index, s in enumerate(segments):
            x0, x1 = sorted((s.x1, s.x2))
            y0, y1 = sorted((s.y1, s.y2))
            for cx in range(self._cell(x0 - reach), self._cell(x1 + reach) + 1):
                for cy in range(self._cell(y0 - reach), self._cell(y1 + reach) + 1):
                    self.cells[(cx, cy)].append(index)

    def _cell(self, value: float) -> int:
        return math.floor(value / self.CELL)

    def near(self, x: float, y: float) -> list[int]:
        return self.cells.get((self._cell(x), self._cell(y)), [])


def page_nets(segments: list[Segment], dots=()) -> list[Net]:
    """Netze aus Leiter-Segmenten. dots: Verbindungspunkte als (x, y, Radius); nur sie verbinden eine Kreuzung."""
    solid = [s for s in segments if not s.dashed and s.length > 0]
    count = len(solid)
    if not count:
        return []
    graph = nx.Graph()
    graph.add_nodes_from(range(count))
    points = np.array([(s.x1, s.y1) for s in solid] + [(s.x2, s.y2) for s in solid])
    attached = np.zeros(2 * count, dtype=bool)
    for i, j in cKDTree(points).query_pairs(SNAP):
        graph.add_edge(i % count, j % count)
        attached[i] = attached[j] = True
    grid = _Grid(solid, max(SNAP, DOT_MAX))
    for k, (x, y) in enumerate(points):
        own = k % count
        for other in grid.near(x, y):
            if other != own and _point_segment(x, y, solid[other]) <= SNAP:
                graph.add_edge(own, other)
                attached[k] = True
    for cx, cy, radius in dots:
        reach = radius + SNAP
        members = [i for i in grid.near(cx, cy) if _point_segment(cx, cy, solid[i]) <= reach]
        for a, b in zip(members, members[1:], strict=False):
            graph.add_edge(a, b)
        for k, (x, y) in enumerate(points):
            if k % count in members and math.hypot(x - cx, y - cy) <= reach:
                attached[k] = True
    nets = []
    for component in nx.connected_components(graph):
        members = sorted(component)
        ends = [
            (float(points[k][0]), float(points[k][1]))
            for i in members
            for k in (i, i + count)
            if not attached[k]
        ]
        nets.append(Net(tuple(solid[i] for i in members), tuple(ends)))
    nets.sort(key=lambda net: (net.segments[0].y1, net.segments[0].x1))
    return nets


# --- Enden benennen ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Anchor:
    """Anschluss-Text mit Position: Knoten-ID wie im Signalgraphen."""

    node: str
    spot: _Spot


def _right(spot: _Spot) -> float:
    return 2 * spot.x - spot.left


def _joined_spots(spots: list[_Spot]) -> list[_Spot]:
    """Klemmleiste und Nummer als zwei Woerter ("X420", "3") zu einem Wort "X420 3" zusammen."""
    joined = []
    for strip in spots:
        if not pdf_layout._STRIP_TOKEN.fullmatch(strip.text):
            continue
        beside = [
            s
            for s in spots
            if s.text.isdigit()
            and abs(s.y - strip.y) <= 1.5
            and 0 <= s.left - _right(strip) <= SPACED_GAP
        ]
        if len(beside) == 1:
            number = beside[0]
            right = _right(number)
            joined.append(
                _Spot(f"{strip.text} {number.text}", (strip.left + right) / 2, strip.y, strip.left)
            )
    return joined


def _addresses(tags: list) -> set[str]:
    """E/A-Bitadressen; "-A1.1" ist eine SPS-Karte, nicht die Adresse A1.1."""
    devices = {t.tag for t in tags if t.tag_type == TagType.DEVICE}
    return {
        t.tag
        for t in tags
        if t.tag_type == TagType.PLC_ADDRESS
        and _BIT.fullmatch(t.tag)
        and f"-{t.tag}" not in devices
    }


def _anchor_node(text: str, spaced: bool) -> str | None:
    """Klemme mit Nummer oder E/A-Adresse, wenn das Wort genau eins davon nennt."""
    tags = extract_tags(text, spaced_terminals=spaced)
    found = {t.tag for t in tags if t.tag_type == TagType.TERMINAL and ":" in t.tag} | _addresses(
        tags
    )
    return found.pop() if len(found) == 1 else None


def _leading(spot: _Spot, spots: list[_Spot]) -> bool:
    """Steht kein Wort direkt davor? Beschriftungen fangen mit der Klemme an ("-X2:1 +24 V"); mitten im Satz ("0 V
    ueber -X3:14") ist sie ein Hinweis auf eine andere Stelle, kein Anschluss."""
    return not any(
        other is not spot
        and abs(other.y - spot.y) <= LINE
        and 0 <= spot.left - _right(other) <= PHRASE_GAP
        for other in spots
    )


def _anchors(spots: list[_Spot], spaced: bool) -> list[_Anchor]:
    anchors = [_Anchor(node, spot) for node, spot in pdf_layout.pin_spots(spots)]
    words = spots + (_joined_spots(spots) if spaced else [])
    for spot in words:
        if (node := _anchor_node(spot.text, spaced)) and _leading(spot, spots):
            anchors.append(_Anchor(node, spot))
    return anchors


def _nearest(x: float, y: float, anchors: list[_Anchor]) -> str | None:
    """Anschluss eines Endes: am naechsten, innerhalb PIN_REACH, das naechste andere Ziel PIN_CLEAR-mal so weit weg."""
    ranked = sorted((math.hypot(a.spot.x - x, a.spot.y - y), a.node) for a in anchors)
    if not ranked or ranked[0][0] > PIN_REACH:
        return None
    best, node = ranked[0]
    other = next((d for d, n in ranked[1:] if n != node), None)
    if other is not None and other < PIN_CLEAR * best:
        return None
    return node


class _Boxes:
    """Symbole einer Seite mit Rasterindex: welches Symbol beruehrt ein Leitungsende?"""

    CELL = 16.0

    def __init__(self, boxes: tuple[_Box, ...]):
        self.boxes = boxes
        self.cells: dict[tuple[int, int], list[int]] = defaultdict(list)
        for index, box in enumerate(boxes):
            for cx in range(self._cell(box.x0 - ROW), self._cell(box.x1 + ROW) + 1):
                for cy in range(self._cell(box.y0 - ROW), self._cell(box.y1 + ROW) + 1):
                    self.cells[(cx, cy)].append(index)

    def _cell(self, value: float) -> int:
        return math.floor(value / self.CELL)

    def touched(self, x: float, y: float) -> tuple[_Box, str] | None:
        """Kleinstes Symbol, auf dessen Rand das Ende liegt; eine Klemme (bis TERMINAL_MAX) auch knapp davor."""
        found = []
        for index in self.cells.get((self._cell(x), self._cell(y)), []):
            box = self.boxes[index]
            small = max(box.x1 - box.x0, box.y1 - box.y0) <= TERMINAL_MAX
            if side := box.on_edge(x, y, ROW if small else SNAP):
                found.append((max(box.x1 - box.x0, box.y1 - box.y0), index, box, side))
        if not found:
            return None
        _size, _index, box, side = min(found)
        return box, side


def _small(box: _Box) -> bool:
    return max(box.x1 - box.x0, box.y1 - box.y0) <= TERMINAL_MAX


def _in_symbol(x: float, y: float, box: _Box, side: str, anchors: list[_Anchor]) -> str | None:
    """Ende am Rand eines Symbols (SPS-Karte): die eine Beschriftung im Symbol auf derselben Hoehe (seitlich) bzw.
    in derselben Spalte (oben/unten)."""
    inside = [a for a in anchors if box.contains(a.spot.x, a.spot.y)]
    if side == "side":
        hits = {a.node for a in inside if abs(a.spot.y - y) <= ROW}
    else:
        hits = {a.node for a in inside if a.spot.left - ROW <= x <= _right(a.spot) + ROW}
    return hits.pop() if len(hits) == 1 else None


def _to_box(x: float, y: float, box: _Box) -> float:
    """Abstand eines Punkts zum Rechteck, 0 im Inneren."""
    return math.hypot(max(box.x0 - x, 0.0, x - box.x1), max(box.y0 - y, 0.0, y - box.y1))


def _box_labels(boxes: tuple[_Box, ...], spots: list[_Spot]) -> dict[_Box, str]:
    """Kennzeichen grosser Symbole ohne Anschlussnummern (Geraet, Leuchte, Motor, Umrichter): das Geraet, das links
    oder rechts neben dem Symbol auf seiner Hoehe steht, bis LABEL_GAP vom Rand. Ein Kennzeichen, das so neben zwei
    Symbolen steht, und ein Symbol mit zwei solchen Kennzeichen bleiben ohne Namen. Stehen Anschlussnummern am Symbol
    (Spule oder Ventil A1/A2), benennen nur sie die Leitungen: Was sonst den Rand beruehrt, ist ein Nachbar."""
    large = list(dict.fromkeys(box for box in boxes if not _small(box)))
    devices = [
        (match.group(1), spot)
        for spot in spots
        if (match := pdf_layout._DEVICE_TOKEN.fullmatch(spot.text))
        and not _STRIP.match(match.group(1))
        and not _CABLE.match(match.group(1))
    ]
    found: dict[_Box, set[str]] = defaultdict(set)
    for tag, spot in devices:
        beside = [
            box
            for box in large
            if box.y0 <= spot.y <= box.y1
            and 0 <= max(box.x0 - _right(spot), spot.left - box.x1) <= LABEL_GAP
        ]
        if len(beside) == 1:
            found[beside[0]].add(tag)
    # Anschlussnummern je naechstem Kennzeichen
    numbered: dict[str, list[_Spot]] = defaultdict(list)
    for number in spots:
        if devices and pdf_layout._PIN.fullmatch(number.text) and _alone(number, spots):
            owner = min(devices, key=lambda d: math.dist((d[1].x, d[1].y), (number.x, number.y)))
            numbered[owner[0]].append(number)
    labels = {}
    for box, tags in found.items():
        if len(tags) != 1:
            continue
        tag = next(iter(tags))
        if not any(_to_box(s.x, s.y, box) <= 2 * LABEL_GAP for s in numbered[tag]):
            labels[box] = tag
    return labels


def _alone(spot: _Spot, spots: list[_Spot]) -> bool:
    """Steht das Wort fuer sich (Anschlussnummer) und nicht in einem Satz ("In 25 A")?"""
    return _leading(spot, spots) and _next_word(spot, spots) is None


def _next_word(spot: _Spot, spots: list[_Spot]) -> _Spot | None:
    """Das Wort, das in derselben Zeile direkt rechts folgt (bis PHRASE_GAP)."""
    after = [
        s
        for s in spots
        if s is not spot and abs(s.y - spot.y) <= LINE and 0 <= s.left - _right(spot) <= PHRASE_GAP
    ]
    return min(after, key=lambda s: s.left) if after else None


def _terminal(text: str, spaced: bool) -> str | None:
    node = _anchor_node(text, spaced)
    return node if node and not _BIT.fullmatch(node) else None


TerminalRun = list[tuple[str, _Spot]]


def _terminal_runs(spots: list[_Spot], spaced: bool) -> list[tuple[TerminalRun, bool]]:
    """Mindestens zwei Klemmen derselben Leiste direkt hintereinander am Anfang einer Zeile ("-X4:U -X4:V -X4:W"),
    dazu, ob die Zeile damit endet (Sammelbeschriftung) oder weitergeht ("-X4:U -X4:V (Leitung -W4)": ein Hinweis)."""
    runs = []
    for spot in spots:
        node = _terminal(spot.text, spaced)
        if not node or not _leading(spot, spots):
            continue
        strip = node.split(":", 1)[0]
        run = [(node, spot)]
        alone = True
        while (following := _next_word(run[-1][1], spots)) is not None:
            found = _terminal(following.text, spaced)
            if not found or found.split(":", 1)[0] != strip:
                alone = False
                break
            run.append((found, following))
        if len(run) >= 2 and len({name for name, _spot in run}) == len(run):
            runs.append((run, alone))
    return runs


def _center(box: _Box) -> tuple[float, float]:
    return (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2


def _listed_terminals(
    lists: list[TerminalRun], boxes: tuple[_Box, ...], anchors: list[_Anchor]
) -> dict[_Box, str]:
    """Namen der Klemmensymbole einer Sammelbeschriftung, von links nach rechts. Gezaehlt werden die Klemmen bis
    PIN_REACH um die Beschriftung, ohne die mit eigener Beschriftung (deren naechste Klemme, PIN_CLEAR-mal naeher als
    jede andere). Es muessen genau so viele sein, wie die Zeile nennt, und sie stehen in einer Reihe (+-ROW)."""
    small = list(dict.fromkeys(box for box in boxes if _small(box)))
    if not lists or not small:
        return {}
    listed = {id(spot) for run in lists for _node, spot in run}
    claimed = set()
    for anchor in anchors:
        if id(anchor.spot) in listed or pin_kind(anchor.node) or _BIT.fullmatch(anchor.node):
            continue
        point = (anchor.spot.x, anchor.spot.y)
        ranked = sorted((math.dist(_center(box), point), i) for i, box in enumerate(small))
        if ranked[0][0] <= PIN_REACH and (
            len(ranked) == 1 or ranked[1][0] >= PIN_CLEAR * ranked[0][0]
        ):
            claimed.add(small[ranked[0][1]])
    names: dict[_Box, str] = {}
    for run in lists:
        words = [spot for _node, spot in run]
        y = sum(spot.y for spot in words) / len(words)
        area = _Box(min(s.left for s in words), y - LINE, max(_right(s) for s in words), y + LINE)
        row = [
            box for box in small if box not in claimed and _to_box(*_center(box), area) <= PIN_REACH
        ]
        heights = [_center(box)[1] for box in row]
        if len(row) != len(run) or max(heights) - min(heights) > ROW or set(row) & set(names):
            continue
        for box, (node, _spot) in zip(sorted(row, key=lambda b: b.x0), run, strict=True):
            names[box] = node
    return names


def _terminal_of(
    x: float, y: float, node: str, anchors: list[_Anchor], small: list[_Box]
) -> _Box | None:
    """Klemmensymbol, zu dem die Beschriftung node am Ende (x, y) gehoert: das naechste zu ihr. Steht sie naeher an
    einer anderen Klemme (etwa "-X4:PE" neben der Nachbarklemme), benennt sie dieses Ende nicht."""
    spot = min(
        (a.spot for a in anchors if a.node == node), key=lambda s: math.hypot(s.x - x, s.y - y)
    )
    return min(small, key=lambda box: math.dist(_center(box), (spot.x, spot.y)), default=None)


def _end_names(
    nets: list[Net],
    boxes: _Boxes,
    anchors: list[_Anchor],
    labels: dict[_Box, str] | None = None,
    terminals: dict[_Box, str] | None = None,
) -> list[list[str | None]]:
    """Name je freiem Ende. Am Rand eines grossen Symbols (Karte, Geraet, Leuchte) zaehlt nur die Beschriftung im
    Symbol: daneben stehen Texte anderer Zeilen. Steht im Symbol kein Anschluss, gilt sein Kennzeichen daneben
    (`_box_labels`). Enden an derselben Klemme (kleines Symbol) teilen ihren Namen, denn die Beschriftung steht nur an
    einer Seite der Klemme; eine Beschriftung benennt nur Enden an ihrer naechsten Klemme (`_terminal_of`), eine Klemme
    aus einer Sammelbeschriftung (`_listed_terminals`) traegt deren Namen."""
    labels = labels or {}
    terminals = terminals or {}
    small = [box for box in boxes.boxes if _small(box)]
    names: list[list[str | None]] = []
    at_terminal: dict[_Box, list[tuple[int, int]]] = defaultdict(list)
    for n, net in enumerate(nets):
        row: list[str | None] = []
        for e, (x, y) in enumerate(net.ends):
            touched = boxes.touched(x, y)
            if touched is None:
                row.append(_nearest(x, y, anchors))
                continue
            box, side = touched
            if _small(box):
                at_terminal[box].append((n, e))
                name = _nearest(x, y, anchors)
                row.append(
                    name if name and _terminal_of(x, y, name, anchors, small) == box else None
                )
            elif any(box.contains(a.spot.x, a.spot.y) for a in anchors):
                row.append(_in_symbol(x, y, box, side, anchors))
            else:
                row.append(labels.get(box))
        names.append(row)
    for box, members in at_terminal.items():
        found = {names[n][e] for n, e in members} - {None}
        shared = terminals.get(box) or (found.pop() if len(found) == 1 else None)
        for n, e in members:
            names[n][e] = shared
    return names


def _role(node: str) -> int:
    """-1 Quelle, 0 neutral, 1 Ziel: E-Adresse und Spule nehmen auf, A-Adresse und Kontakt geben ab."""
    if _BIT.fullmatch(node):
        return 1 if node[0] == "E" else -1
    kind = pin_kind(node)
    if kind == "Spule":
        return 1
    return -1 if kind else 0


def _net_edges(names: list[str], page: int, via: str) -> list[PlanEdge]:
    """Kanten zwischen den benannten Enden eines Netzes. Quelle -> Ziel direkt nur, wenn keine Klemme dazwischen
    steht; gleiche Rollen bleiben ungerichtet."""
    roles = {name: _role(name) for name in names}
    neutral = any(role == 0 for role in roles.values())
    edges = []
    for a, b in combinations(sorted(names), 2):
        if roles[a] == roles[b]:
            edges.append(PlanEdge(a, b, page, via, directed=False))
        elif {roles[a], roles[b]} == {-1, 1} and neutral:
            continue
        else:
            source, target = (a, b) if roles[a] < roles[b] else (b, a)
            edges.append(PlanEdge(source, target, page, via, directed=True))
    return edges


def _is_rail(net: Net, size: tuple[float, float]) -> bool:
    width, height = size
    for s in net.segments:
        if abs(s.x2 - s.x1) > RAIL_SHARE * width or abs(s.y2 - s.y1) > RAIL_SHARE * height:
            return True
    return False


def _beside(nets: list[Net], anchors: list[_Anchor]) -> dict[int, list[str]]:
    """Klemmen und Adressen, die neben einer durchlaufenden Leitung stehen (Kanaele in Spalten, die Leitung laeuft
    durch Klemme und Eingang): je Netz, wenn das Netz bis BESIDE weg liegt und jedes andere PIN_CLEAR-mal so weit."""
    segments = [(n, s) for n, net in enumerate(nets) for s in net.segments]
    grid = _Grid([s for _n, s in segments], BESIDE * PIN_CLEAR)
    found: dict[int, list[str]] = defaultdict(list)
    for anchor in anchors:
        if pin_kind(anchor.node):
            continue  # Anschlussnummern stehen am Ende ihrer Leitung, nicht daneben
        x, y = anchor.spot.x, anchor.spot.y
        nearest: dict[int, float] = {}
        for index in grid.near(x, y):
            n, s = segments[index]
            nearest[n] = min(nearest.get(n, math.inf), _point_segment(x, y, s))
        ranked = sorted((d, n) for n, d in nearest.items())
        if not ranked or ranked[0][0] > BESIDE:
            continue
        if len(ranked) > 1 and ranked[1][0] < PIN_CLEAR * ranked[0][0]:
            continue
        found[ranked[0][1]].append(anchor.node)
    return found


def _wire_edges(
    geometry: _Geometry, segments: list[Segment], page: int, spaced: bool
) -> list[PlanEdge]:
    spots = list(geometry.spots)
    anchors = _anchors(spots, spaced)
    labels = _box_labels(geometry.boxes, spots)
    if not anchors and not labels:
        return []
    runs = _terminal_runs(spots, spaced)
    terminals = _listed_terminals([run for run, alone in runs if alone], geometry.boxes, anchors)
    # Eine Zeile mit mehreren Klemmen steht nicht am Ende einer bestimmten Leitung: Sie benennt hoechstens Klemmen
    listed = {id(spot) for run, _alone in runs for _node, spot in run}
    anchors = [anchor for anchor in anchors if id(anchor.spot) not in listed]
    nets = page_nets(segments, geometry.dots)
    beside = _beside(nets, anchors)
    edges: list[PlanEdge] = []
    ends_named = _end_names(nets, _Boxes(geometry.boxes), anchors, labels, terminals)
    for n, (net, ends) in enumerate(zip(nets, ends_named, strict=True)):
        names = _without_own_device(
            list(dict.fromkeys([name for name in ends if name] + beside.get(n, [])))
        )
        if len(names) < 2 or len(names) > MAX_ENDS or _is_rail(net, geometry.size):
            continue
        edges += _net_edges(names, page, "leitung")
    return _unique(edges)


def _without_own_device(names: list[str]) -> list[str]:
    """Ein Anschluss schlaegt sein Geraet: Die Zuleitung einer Spule laeuft von "-K1:A1" an den Rand von "-K1"."""
    devices = {name.split(":", 1)[0] for name in names if pin_kind(name)}
    return [name for name in names if name not in devices]


def _unique(edges: list[PlanEdge]) -> list[PlanEdge]:
    """Gleiche Verbindung aus zwei Netzen einer Seite nur einmal; gerichtet schlaegt ungerichtet."""
    seen: dict[tuple[str, str], PlanEdge] = {}
    for edge in edges:
        key = tuple(sorted((edge.source, edge.target)))
        if key not in seen or (edge.directed and not seen[key].directed):
            seen[key] = edge
    return sorted(seen.values(), key=lambda e: (e.page, e.source, e.target))


# --- Lage im Plan ----------------------------------------------------------------------------

Channel = tuple[str, str, str | None]  # Adresse, Klemme, Feldgeraet oder Anschluss


def _channel(items: list[tuple[float, str]], spaced: bool) -> Channel | None:
    """Kanal aus Beschriftungen mit ihrer Lage entlang des Kanals (x in einer Zeile, Hoehe in einer Spalte); None,
    wenn Adresse oder Klemme nicht eindeutig sind. Das Feldgeraet steht jenseits der Klemme, von der Adresse aus
    gesehen; die SPS-Karte bei der Adresse und Leitungen (-W) zaehlen nicht. Mehr als ein Kandidat: kein Feldgeraet."""
    found = [
        (pos, tag) for pos, text in items for tag in extract_tags(text, spaced_terminals=spaced)
    ]
    tags = [tag for _pos, tag in found]
    # "(A20.2)" unter einem Schuetz verweist auf den Ausgang, der seine Spule schaltet: keine Adresse des Kanals
    plain = [tag for _pos, text in items for tag in extract_tags(_REFERENCE.sub(" ", text))]
    addresses = _addresses(tags) & _addresses(plain)
    terminals = {t.tag for t in tags if t.tag_type == TagType.TERMINAL and ":" in t.tag}
    if len(addresses) != 1 or len(terminals) != 1:
        return None
    address, terminal = addresses.pop(), terminals.pop()
    at = min(pos for pos, tag in found if tag.tag == address)
    via = min(pos for pos, tag in found if tag.tag == terminal)
    side = (via > at) - (via < at)
    beyond = [tag for pos, tag in found if side and (pos - via) * side > 0]
    pins = {
        t.tag
        for t in beyond
        if t.tag_type == TagType.DEVICE_PIN
        and pin_kind(t.tag)
        and not _CARD.match(t.tag.split(":")[0])
    }
    devices = {
        t.tag
        for t in beyond
        if t.tag_type == TagType.DEVICE and not _CARD.match(t.tag) and not _CABLE.match(t.tag)
    }
    candidates = pins or devices
    return address, terminal, candidates.pop() if len(candidates) == 1 else None


def _channel_edges(channels: list[Channel], page: int) -> list[PlanEdge]:
    edges = []
    for address, terminal, field in channels:
        chain = [field, terminal, address] if address[0] == "E" else [address, terminal, field]
        chain = [node for node in chain if node]
        edges += [
            PlanEdge(a, b, page, "lage", True) for a, b in zip(chain, chain[1:], strict=False)
        ]
    return edges


def _row_channels(spots: list[_Spot], spaced: bool) -> list[Channel]:
    """Kanaele in Zeilen: Woerter auf der Linie durch Adresse und Klemme (+-ROW). Die Linie folgt der Klemme, weil ein
    schief eingescanntes Blatt ueber die Zeilenlaenge mehr als ROW abfaellt (bis SKEW, etwa 1 Grad)."""
    channels = []
    for spot in spots:
        node = _anchor_node(spot.text, False)
        if not node or not _BIT.fullmatch(node):
            continue
        terminals = [
            s
            for s in spots
            if s is not spot
            and abs(s.y - spot.y) <= ROW + SKEW * abs(s.x - spot.x)
            and (found := _anchor_node(s.text, spaced))
            and not _BIT.fullmatch(found)
        ]
        if not terminals:
            continue
        terminal = min(terminals, key=lambda s: abs(s.x - spot.x))
        slope = (terminal.y - spot.y) / (terminal.x - spot.x) if terminal.x != spot.x else 0.0
        # waagerecht oder entlang der Klemme: Auf Vektorblaettern steht die Klemmenbeschriftung oft ueber der Leitung
        row = [
            (s.x, s.text)
            for s in spots
            if min(abs(s.y - spot.y), abs(s.y - spot.y - slope * (s.x - spot.x))) <= ROW
        ]
        if (channel := _channel(row, spaced)) and channel[0] == node:
            channels.append(channel)
    return list(dict.fromkeys(channels))


def _column_channels(page: pdfium.PdfPage, spaced: bool) -> list[Channel]:
    """Kanaele in Spalten (#90): die Beschriftungen je Strompfad aus pdf_layout, von oben nach unten."""
    layout = pdf_layout.column_layout(page)
    if layout is None:
        return []
    channels = []
    for column in sorted({n for n, _segment in layout.placed}):
        items = [
            (min(t.top for t in segment), " ".join(t.text for t in segment))
            for n, segment in layout.placed
            if n == column
        ]
        if channel := _channel(items, spaced):
            channels.append(channel)
    return channels


def _layout_edges(
    page: pdfium.PdfPage, spots: list[_Spot], number: int, spaced: bool
) -> list[PlanEdge]:
    channels = _column_channels(page, spaced) or _row_channels(spots, spaced)
    if len(channels) < LAGE_MIN:
        return []
    return _unique(_channel_edges(channels, number))


# --- Dokument ---------------------------------------------------------------------------------


def _spaced_style(path: Path) -> bool:
    """Klemmen als "X420 3" (Schweizer Elektroschema) im ganzen Dokument? Wie tags.detect_spaced_terminals."""
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            text = "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
        finally:
            pdf.close()
    return detect_spaced_terminals(text)


def page_wire_edges(path: Path, page: int, spaced: bool | None = None) -> list[PlanEdge]:
    """Kanten aus den Leitungen einer Seite (via "leitung"); [] ohne Leiter oder ohne benannte Enden."""
    geometry = _geometry(path, page)
    if geometry is None:
        return []
    segments = page_segments(path, page)
    if spaced is None:
        spaced = _spaced_style(path)
    return _wire_edges(geometry, segments, page, spaced)


def _page_count(path: Path) -> int:
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()


def _layout_page(path: Path, page: int, spots: list[_Spot], spaced: bool) -> list[PlanEdge]:
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            return _layout_edges(pdf[page - 1], spots, page, spaced)
        finally:
            pdf.close()


def _device(node: str) -> str:
    """Anschluss -> Geraet ("-S1:14" -> "-S1"); Klemmen und Adressen bleiben."""
    return node.split(":", 1)[0] if pin_kind(node) else node


def compute_edges(path: Path) -> list[PlanEdge]:
    """Alle Seiten ohne Cache: Leitungen, dazu die Lage im Plan fuer jede Verbindung, die keine Leitung schon zeigt.

    Kanalblaetter tragen oft Leitungen, die durch Klemme und Eingang laufen, ohne dass jedes Ende benannt ist; die Lage
    (Feldgeraet, Klemme, Adresse in einer Spalte oder Zeile) ergaenzt dort, was die Leitungen offen lassen. Ob zwei
    Knoten schon verbunden sind, gilt im ganzen Dokument und fuer Anschluss und Geraet gleich (-S1:14 wie -S1)."""
    spaced = _spaced_style(path)
    wired: list[PlanEdge] = []
    placed: list[PlanEdge] = []
    for page in range(1, _page_count(path) + 1):
        segments = page_segments(path, page)
        geometry = _geometry(path, page)
        if geometry is None:
            continue
        if any(not s.dashed for s in segments):
            wired += _wire_edges(geometry, segments, page, spaced)
        placed += _layout_page(path, page, list(geometry.spots), spaced)
    shown = {frozenset((_device(e.source), _device(e.target))) for e in wired}
    extra = [e for e in placed if frozenset((_device(e.source), _device(e.target))) not in shown]
    return sorted(wired + extra, key=lambda e: (e.page, e.via, e.source, e.target))


def plan_edges(path: Path) -> list[PlanEdge]:
    """Kanten eines Stromlaufplan-PDFs, einmal je Dateiinhalt und Leser-Version gerechnet (data/plan_cache)."""
    cached = read_edges(path)
    if cached is not None:
        return cached
    edges = compute_edges(path)
    write_edges(path, edges)
    return edges
